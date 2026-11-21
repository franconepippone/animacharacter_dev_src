from __future__ import annotations

import threading
import time

import pytest
from lifecycle_pkg.events import (
    FaultEnteredEvent,
    LifecycleEvent,
    RecoveryAttemptEvent,
    RunnerExitedEvent,
    TargetStateChangedEvent,
    TransitionCompletedEvent,
)
from lifecycle_pkg import (
    BackoffConfig,
    LifecycleRunner,
    LifecycleThreadedRunner,
    RecoveryResult,
    RecoveryResultStatus,
    State,
    TransitionResult,
)
from tests.conftest import RecordedDevice


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[LifecycleEvent] = []
        self._condition = threading.Condition()

    def emit(self, event: LifecycleEvent) -> None:
        with self._condition:
            self.events.append(event)
            self._condition.notify_all()

    def wait_for(self, event_type: type[LifecycleEvent], count: int = 1) -> None:
        with self._condition:
            assert self._condition.wait_for(
                lambda: sum(
                    isinstance(event, event_type) for event in self.events
                )
                >= count,
                timeout=2.0,
            )

    def matching(self, event_type: type[LifecycleEvent]) -> list[LifecycleEvent]:
        with self._condition:
            return [
                event
                for event in self.events
                if isinstance(event, event_type)
            ]


def test_runner_reaches_active_runs_and_exits_on_finalized(
    device: RecordedDevice,
) -> None:
    first_tick_started = threading.Event()
    device.on_run_started = first_tick_started

    runner = LifecycleRunner(
        device,
        initial_target=State.ACTIVE,
        backoff_config=BackoffConfig(retry_base_delay=0.0, recover_base_delay=0.0, fault_entry_delay=0.0),
    )

    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()

    assert first_tick_started.wait(timeout=2.0)
    assert runner.lc.state == State.ACTIVE

    runner.set_target_state(State.FINALIZED)
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert runner.lc.state == State.FINALIZED
    assert "deactivate" in device.events
    assert "shutdown" in device.events


def test_runner_waits_without_busy_polling_at_non_active_target(
    device: RecordedDevice,
) -> None:
    runner = LifecycleRunner(device, initial_target=State.INACTIVE)

    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()

    # Wait briefly for runner to reach INACTIVE and block on condition wait
    deadline = time.monotonic() + 1.0
    while runner.lc.state != State.INACTIVE and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runner.lc.state == State.INACTIVE

    run_count_before = device.run_ticks_executed
    time.sleep(0.05)
    assert device.run_ticks_executed == run_count_before

    # Transition to FINALIZED to let thread exit cleanly
    runner.set_target_state(State.FINALIZED)
    thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_runner_recovers_from_fault_and_continues_to_target(
    device: RecordedDevice,
) -> None:
    recovered_event = threading.Event()

    def _on_recover_side_effect() -> None:
        recovered_event.set()

    device.activate_results = [RuntimeError("arming failed")]
    device.recover_results = [RecoveryResult.success(State.INACTIVE)]

    runner = LifecycleRunner(
        device,
        initial_target=State.INACTIVE,
        backoff_config=BackoffConfig(retry_base_delay=0.0, recover_base_delay=0.0, fault_entry_delay=0.0),
    )

    # Intercept recover call to signal completion
    orig_on_recover = device.on_recover

    def _wrapped_recover(fault):
        res = orig_on_recover(fault)
        recovered_event.set()
        return res

    device.on_recover = _wrapped_recover  # type: ignore[method-assign]

    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()

    # Move to ACTIVE so ACTIVATE fails and enters FAULTED, then set target to INACTIVE
    runner.set_target_state(State.ACTIVE)
    assert recovered_event.wait(timeout=2.0)
    runner.set_target_state(State.INACTIVE)

    deadline = time.monotonic() + 2.0
    while runner.lc.state != State.INACTIVE and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runner.lc.state == State.INACTIVE

    runner.set_target_state(State.FINALIZED)
    thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_runner_rejects_faulted_as_target_state(device: RecordedDevice) -> None:
    runner = LifecycleRunner(device, initial_target=State.INACTIVE)
    with pytest.raises(ValueError):
        runner.set_target_state(State.FAULTED)


def test_get_live_state_tracks_runner_progress(device: RecordedDevice) -> None:
    runner = LifecycleRunner(device, initial_target=State.INACTIVE)
    assert runner.get_live_state() == State.UNCONFIGURED

    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 1.0
    while (
        runner.get_live_state() != State.INACTIVE
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)

    assert runner.get_live_state() == State.INACTIVE
    runner.set_target_state(State.FINALIZED)
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert runner.get_live_state() == State.FINALIZED


def test_runner_emits_target_state_changes(device: RecordedDevice) -> None:
    sink = RecordingEventSink()
    runner = LifecycleRunner(
        device, initial_target=State.INACTIVE, event_sink=sink
    )

    runner.set_target_state(State.FINALIZED)
    sink.wait_for(TargetStateChangedEvent, count=2)

    changes = sink.matching(TargetStateChangedEvent)
    assert changes[0].previous_target is None
    assert changes[0].new_target == State.INACTIVE
    assert changes[1].previous_target == State.INACTIVE
    assert changes[1].new_target == State.FINALIZED


def test_runner_emits_progress_fault_recovery_and_exit_events(
    device: RecordedDevice,
) -> None:
    sink = RecordingEventSink()
    allow_run_tick = threading.Event()
    device.allow_run_tick = allow_run_tick
    device.activate_results = [RuntimeError("activation failed")]
    device.recover_results = [
        RecoveryResult.failed(),
        RecoveryResult.success(State.INACTIVE),
    ]

    runner = LifecycleRunner(
        device,
        initial_target=State.ACTIVE,
        backoff_config=BackoffConfig(
            retry_base_delay=0.01,
            recover_base_delay=0.01,
            fault_entry_delay=0.01,
        ),
        event_sink=sink,
    )
    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()

    try:
        sink.wait_for(RecoveryAttemptEvent, count=2)
        runner.set_target_state(State.FINALIZED)
        allow_run_tick.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        sink.wait_for(RunnerExitedEvent)
    finally:
        allow_run_tick.set()
        thread.join(timeout=2.0)

    transitions = sink.matching(TransitionCompletedEvent)
    assert any(
        event.transition_id.name == "AWAKE"
        and event.result == TransitionResult.SUCCESS
        for event in transitions
    )
    assert any(
        event.transition_id.name == "ACTIVATE"
        and event.result == TransitionResult.ERROR
        for event in transitions
    )
    faults = sink.matching(FaultEnteredEvent)
    assert len(faults) == 1
    assert faults[0].transition_id.name == "ACTIVATE"
    recovery_attempts = sink.matching(RecoveryAttemptEvent)
    assert [event.attempt_n for event in recovery_attempts] == [1, 2]
    assert [event.status for event in recovery_attempts] == [
        RecoveryResultStatus.FAIL,
        RecoveryResultStatus.SUCCESS,
    ]
    assert sink.matching(RunnerExitedEvent)[0].final_state == State.FINALIZED


def test_runner_emits_events_directly_to_sink(device: RecordedDevice) -> None:
    emitting_threads: list[threading.Thread] = []

    class ThreadRecordingSink:
        def emit(self, event: LifecycleEvent) -> None:
            emitting_threads.append(threading.current_thread())

    runner = LifecycleRunner(
        device,
        initial_target=State.INACTIVE,
        event_sink=ThreadRecordingSink(),
    )
    runner.set_target_state(State.FINALIZED)

    assert emitting_threads == [threading.current_thread()] * 2


def test_failing_event_sink_does_not_disrupt_runner(
    device: RecordedDevice,
) -> None:
    class FailingSink:
        def emit(self, event: LifecycleEvent) -> None:
            raise RuntimeError("event transport unavailable")

    runner = LifecycleRunner(
        device,
        initial_target=State.INACTIVE,
        event_sink=FailingSink(),
    )
    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 1.0
    while runner.lc.state != State.INACTIVE and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runner.lc.state == State.INACTIVE

    runner.set_target_state(State.FINALIZED)
    thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_threaded_runner_owns_and_joins_its_worker(
    device: RecordedDevice,
) -> None:
    tick_started = threading.Event()
    allow_tick_to_finish = threading.Event()
    device.on_run_started = tick_started
    device.allow_run_tick = allow_tick_to_finish
    runner = LifecycleThreadedRunner(
        device,
        initial_target=State.ACTIVE,
        thread_name="test-lifecycle-runner",
    )

    runner.start()
    assert tick_started.wait(timeout=2.0)
    assert runner.is_alive()
    assert runner.join(timeout=0.01) is False

    runner.set_target_state(State.FINALIZED)
    allow_tick_to_finish.set()
    assert runner.join(timeout=2.0)
    assert not runner.is_alive()
    assert runner.get_live_state() == State.FINALIZED

    with pytest.raises(RuntimeError, match="finalized"):
        runner.start()