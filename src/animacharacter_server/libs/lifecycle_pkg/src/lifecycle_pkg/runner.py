"""Thread-safe runner for a lifecycle wrapper."""

from __future__ import annotations

import logging
import threading

from .events import (
    EventSink,
    FaultEnteredEvent,
    LifecycleEvent,
    LogLevel,
    NullEventSink,
    RecoveryAttemptEvent,
    RunnerExitedEvent,
    TargetStateChangedEvent,
    TransitionCompletedEvent,
)
from .reconcile import (
    DEFAULT_BACKOFF_CONFIG,
    BackoffConfig,
    reconcile_step,
)
from .routing import (
    NEXT_TRANSITION_MAP,
    TRANSITION_MAP,
    _validate_reachable_target,
)
from .types import RecoveryResultStatus, State, TransitionId, TransitionResult
from .wrapper import LifecyclableWrapper, Lifecyclable


_LOGGER = logging.getLogger(__name__)


class LifecycleRunner:
    """Drive a lifecycle component toward a thread-safe target state."""

    def __init__(
        self,
        lifecyclable: Lifecyclable,
        initial_target: State = State.ACTIVE,
        backoff_config: BackoffConfig = DEFAULT_BACKOFF_CONFIG,
        event_sink: EventSink | None = None,
    ) -> None:
        """Initialize target state, backoff, and optional event sink."""
        self.lc = LifecyclableWrapper(lifecyclable)
        _validate_reachable_target(self.lc.state, initial_target)
        self.backoff_config = backoff_config
        self._event_sink = (
            event_sink if event_sink is not None else NullEventSink()
        )
        self._cond = threading.Condition()
        self._target_state = initial_target
        self._target_version = 0
        self._emit(
            TargetStateChangedEvent(
                previous_target=None,
                new_target=initial_target,
                message="Initial target state set",
            )
        )

    def set_target_state(self, target_state: State) -> None:
        """Update the target state and wake the runner."""
        _validate_reachable_target(self.lc.state, target_state)
        event: TargetStateChangedEvent | None = None
        with self._cond:
            if target_state != self._target_state:
                previous_target = self._target_state
                self._target_state = target_state
                self._target_version += 1
                self._cond.notify_all()
                event = TargetStateChangedEvent(
                    previous_target=previous_target,
                    new_target=target_state,
                    message="Target state changed",
                )
        if event is not None:
            self._emit(event)

    def get_target_state(self) -> State:
        """Return the current target state."""
        with self._cond:
            return self._target_state

    def _wait_for_target_change(
        self, observed_version: int, timeout: float | None = None
    ) -> bool:
        """Wait for a target change or timeout."""
        with self._cond:
            if self._target_version != observed_version:
                return True
            return self._cond.wait(timeout=timeout)

    def run(self) -> None:
        """Run reconciliation until the wrapper reaches FINALIZED."""
        try:
            while self.lc.state != State.FINALIZED:
                with self._cond:
                    target = self._target_state
                    version = self._target_version

                state = self.lc.state
                if state == target and state == State.ACTIVE:
                    result = self.lc.run()
                    self._emit_transition(
                        TransitionId.RUN, State.ACTIVE, result
                    )
                    self._emit_fault_if_entered(State.ACTIVE)
                    continue

                if state == State.FAULTED:
                    fault = self.lc.current_fault
                    attempt_n = fault.current_n if fault is not None else 1
                    outcome = reconcile_step(
                        self.lc, target, self.backoff_config
                    )
                    recovered = self.lc.state != State.FAULTED
                    self._emit(
                        RecoveryAttemptEvent(
                            attempt_n=attempt_n,
                            status=(
                                RecoveryResultStatus.SUCCESS
                                if recovered
                                else RecoveryResultStatus.FAIL
                            ),
                            new_state=self.lc.state if recovered else None,
                            message=(
                                "Recovery succeeded"
                                if recovered
                                else "Recovery failed"
                            ),
                        )
                    )
                    if not recovered and outcome.retry_delay > 0:
                        self._wait_for_target_change(
                            version, timeout=outcome.retry_delay
                        )
                    continue

                if state == target:
                    self._wait_for_target_change(version)
                    continue

                transition_id = NEXT_TRANSITION_MAP[(state, target)]
                outcome = reconcile_step(
                    self.lc, target, self.backoff_config
                )
                self._emit_transition(
                    transition_id,
                    state,
                    (
                        TransitionResult.ERROR
                        if self.lc.state == State.FAULTED
                        else TransitionResult.SUCCESS
                        if outcome.progressed
                        else TransitionResult.FAIL_RETRY
                    ),
                )
                self._emit_fault_if_entered(state)

                if not outcome.progressed and outcome.retry_delay > 0:
                    self._wait_for_target_change(
                        version, timeout=outcome.retry_delay
                    )
        finally:
            self._emit(
                RunnerExitedEvent(
                    final_state=self.lc.state,
                    message="Lifecycle runner exited",
                )
            )

    def _emit(self, event: LifecycleEvent) -> None:
        try:
            self._event_sink.emit(event)
        except Exception:
            _LOGGER.exception("Lifecycle event sink failed")

    def _emit_transition(
        self,
        transition_id: TransitionId,
        state_from: State,
        result: TransitionResult,
    ) -> None:
        state_to = TRANSITION_MAP[transition_id][1]
        fault = (
            self.lc.current_fault
            if result == TransitionResult.ERROR
            else None
        )
        self._emit(
            TransitionCompletedEvent(
                transition_id=transition_id,
                state_from=state_from,
                state_to=state_to,
                result=result,
                exception=fault.exception if fault is not None else None,
                message=f"{transition_id.name} transition completed",
            )
        )

    def _emit_fault_if_entered(self, previous_state: State) -> None:
        fault = self.lc.current_fault
        if (
            previous_state != State.FAULTED
            and self.lc.state == State.FAULTED
            and fault is not None
        ):
            self._emit(
                FaultEnteredEvent(
                    transition_id=fault.transition_id,
                    exception=fault.exception,
                    level=LogLevel.ERROR,
                    message=f"Fault entered during {fault.transition_id.name}",
                )
            )
