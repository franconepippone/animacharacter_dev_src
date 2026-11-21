from __future__ import annotations

import threading
import time

import pytest

from lifecycle_pkg import (
    BackoffConfig,
    LifecycleRunner,
    RecoveryResult,
    State,
    TransitionResult,
)
from tests.conftest import RecordedDevice


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