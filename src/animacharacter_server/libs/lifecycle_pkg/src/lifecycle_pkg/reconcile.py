"""Backoff configuration and one-step reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

from .routing import (
    NEXT_TRANSITION_MAP,
    _validate_reachable_target,
)
from .types import State, TransitionResult
from .wrapper import LifecyclableWrapper


@dataclass(frozen=True)
class BackoffConfig:
    """Backoff delays, in seconds, for retries and recovery."""

    retry_base_delay: float = 0.05
    retry_multiplier: float = 2.0
    retry_max_delay: float = 1.0
    recover_base_delay: float = 0.05
    recover_multiplier: float = 2.0
    recover_max_delay: float = 1.0
    fault_entry_delay: float = 0.05

    def __post_init__(self) -> None:
        """Validate all non-negative delays and multiplier values."""
        for name, value in (
            ("retry_base_delay", self.retry_base_delay),
            ("retry_max_delay", self.retry_max_delay),
            ("recover_base_delay", self.recover_base_delay),
            ("recover_max_delay", self.recover_max_delay),
            ("fault_entry_delay", self.fault_entry_delay),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")
        for name, value in (
            ("retry_multiplier", self.retry_multiplier),
            ("recover_multiplier", self.recover_multiplier),
        ):
            if value < 1.0:
                raise ValueError(f"{name} must be >= 1.0, got {value}")

    @staticmethod
    def _compute_delay(
        attempt: int, base: float, multiplier: float, max_delay: float
    ) -> float:
        """Compute a bounded exponential delay for a 1-based attempt."""
        if base == 0.0 or max_delay == 0.0:
            return 0.0
        exponent = max(attempt - 1, 0)
        raw = base * (multiplier ** min(exponent, 30))
        return min(raw, max_delay)

    def retry_delay_for(self, attempt: int) -> float:
        """Return the retry delay for a 1-based attempt."""
        return self._compute_delay(
            attempt, self.retry_base_delay,
            self.retry_multiplier, self.retry_max_delay,
        )

    def recover_delay_for(self, attempt: int) -> float:
        """Return the recovery delay for a 1-based attempt."""
        return self._compute_delay(
            attempt, self.recover_base_delay,
            self.recover_multiplier, self.recover_max_delay,
        )


DEFAULT_BACKOFF_CONFIG = BackoffConfig()


@dataclass(frozen=True)
class ReconcileOutcome:
    """Result of one reconciliation step."""

    progressed: bool
    retry_delay: float = 0.0


def reconcile_step(
    wrapper: LifecyclableWrapper,
    target_state: State,
    backoff: BackoffConfig = DEFAULT_BACKOFF_CONFIG,
) -> ReconcileOutcome:
    """Advance a wrapper by at most one transition or recovery attempt."""
    current = wrapper.state
    _validate_reachable_target(current, target_state)

    if current == State.FAULTED:
        fault = wrapper.current_fault
        result = wrapper.run_recover()
        if wrapper.state != State.FAULTED:
            return ReconcileOutcome(progressed=True)
        attempt = fault.current_n if fault is not None else 1
        return ReconcileOutcome(
            progressed=False,
            retry_delay=backoff.recover_delay_for(attempt),
        )

    if current == target_state:
        return ReconcileOutcome(progressed=False)

    transition_id = NEXT_TRANSITION_MAP[(current, target_state)]
    result = wrapper.transition(transition_id)

    if result == TransitionResult.SUCCESS:
        return ReconcileOutcome(progressed=True)
    if wrapper.state == State.FAULTED:
        return ReconcileOutcome(
            progressed=False,
            retry_delay=backoff.fault_entry_delay,
        )
    if result == TransitionResult.FAIL_RETRY:
        return ReconcileOutcome(
            progressed=False,
            retry_delay=backoff.retry_delay_for(1),
        )
    return ReconcileOutcome(
        progressed=False,
        retry_delay=backoff.retry_delay_for(1),
    )
