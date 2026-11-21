"""State wrapper for lifecycle transitions and fault recovery."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .hooks import Lifecyclable, get_hook_from_transition_id
from .routing import TRANSITION_MAP
from .types import (
    FaultContext,
    RecoveryResult,
    RecoveryResultStatus,
    State,
    TransitionId,
    TransitionResult,
)


class LifecyclableWrapper:
    """Enforce lifecycle rules around a Lifecyclable implementation."""

    @dataclass
    class FaultData:
        """Mutable attempt data retained while faulted."""

        transition_id: TransitionId
        exception: Exception | None
        current_n: int = 1

        def get_attempt_and_increment(self) -> int:
            """Return the current attempt number, then increment it."""
            attempt = self.current_n
            self.current_n += 1
            return attempt

    def __init__(self, lifecyclable_object: Lifecyclable) -> None:
        """Initialize an unconfigured wrapper."""
        self._state_lock = threading.Lock()
        self._state = State.UNCONFIGURED
        self.target: Lifecyclable = lifecyclable_object
        self.current_fault: LifecyclableWrapper.FaultData | None = None

    @property
    def state(self) -> State:
        """Return the current lifecycle state safely across threads."""
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, value: State) -> None:
        with self._state_lock:
            self._state = value

    def _set_faulted(
        self, transition_id: TransitionId, cause_exception: Exception | None
    ) -> None:
        """Enter the faulted state and retain fault details."""
        self.current_fault = self.FaultData(
            transition_id=transition_id,
            exception=cause_exception,
        )
        self.state = State.FAULTED

    def _apply_step_result(
        self,
        transition_id: TransitionId,
        destination_state: State,
        result: TransitionResult,
        exc: Exception | None,
    ) -> TransitionResult:
        """Apply a hook outcome to wrapper state."""
        if not isinstance(result, TransitionResult):
            raise TypeError(
                f"Expected TransitionResult from {transition_id}, "
                f"got {type(result).__name__}"
            )
        if result == TransitionResult.SUCCESS:
            self.state = destination_state
            return TransitionResult.SUCCESS
        if result == TransitionResult.FAIL_RETRY:
            return TransitionResult.FAIL_RETRY
        self._set_faulted(transition_id, exc)
        return TransitionResult.ERROR

    def transition(self, transition_id: TransitionId) -> TransitionResult:
        """Execute one transition if it is valid from the current state."""
        if transition_id not in TRANSITION_MAP:
            raise ValueError(f"Unknown transition_id: {transition_id}")

        state_from, state_to = TRANSITION_MAP[transition_id]
        if state_from != self.state:
            raise ValueError(
                f"{transition_id} is only available from {state_from}, "
                f"not {self.state}"
            )

        hook = get_hook_from_transition_id(self.target, transition_id)
        exc: Exception | None = None
        result: TransitionResult
        try:
            result = hook()
        except Exception as error:
            exc = error
            result = TransitionResult.ERROR
        return self._apply_step_result(
            transition_id, state_to, result, exc
        )

    def run(self) -> TransitionResult:
        """Execute one runtime tick while active."""
        if self.state != State.ACTIVE:
            raise RuntimeError(
                f"Cannot run when state is {self.state}; expected ACTIVE"
            )

        exc: Exception | None = None
        result: TransitionResult
        try:
            run_hook = get_hook_from_transition_id(
                self.target, TransitionId.RUN
            )
            result = run_hook()
        except Exception as error:
            exc = error
            result = TransitionResult.ERROR
        return self._apply_step_result(
            TransitionId.RUN, State.ACTIVE, result, exc
        )

    def run_recover(self) -> RecoveryResult:
        """Attempt one recovery action while faulted."""
        if self.state != State.FAULTED or self.current_fault is None:
            raise RuntimeError(
                "Cannot recover: state is not FAULTED or fault data is missing"
            )

        fault = FaultContext(
            transition_id=self.current_fault.transition_id,
            attempt_n=self.current_fault.get_attempt_and_increment(),
            exception=self.current_fault.exception,
        )

        result: RecoveryResult
        try:
            result = self.target.on_recover(fault)
        except Exception:
            return RecoveryResult.failed()

        if not isinstance(result, RecoveryResult):
            raise TypeError(
                "Expected a RecoveryResult instance from on_recover, "
                f"got {type(result).__name__}"
            )
        if result.status == RecoveryResultStatus.SUCCESS:
            if (
                result.new_state is None
                or not isinstance(result.new_state, State)
                or result.new_state == State.FAULTED
            ):
                raise ValueError(
                    "Successful recovery must specify a valid non-FAULTED state"
                )
            self.state = result.new_state
            self.current_fault = None
            return result
        return RecoveryResult.failed()
