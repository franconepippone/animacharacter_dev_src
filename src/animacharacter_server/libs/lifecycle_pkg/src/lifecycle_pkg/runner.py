"""Thread-safe runner for a lifecycle wrapper."""

from __future__ import annotations

import threading

from .reconcile import (
    DEFAULT_BACKOFF_CONFIG,
    BackoffConfig,
    reconcile_step,
)
from .routing import _validate_reachable_target
from .types import State
from .wrapper import LifecyclableWrapper, Lifecyclable


class LifecycleRunner:
    """Drive a lifecycle component toward a thread-safe target state."""

    def __init__(
        self,
        lifecyclable: Lifecyclable,
        initial_target: State = State.ACTIVE,
        backoff_config: BackoffConfig = DEFAULT_BACKOFF_CONFIG,
    ) -> None:
        """Initialize target state and reconciliation backoff."""
        self.lc = LifecyclableWrapper(lifecyclable)
        _validate_reachable_target(self.lc.state, initial_target)
        self.backoff_config = backoff_config
        self._cond = threading.Condition()
        self._target_state = initial_target
        self._target_version = 0

    def set_target_state(self, target_state: State) -> None:
        """Update the target state and wake the runner."""
        _validate_reachable_target(self.lc.state, target_state)
        with self._cond:
            if target_state != self._target_state:
                self._target_state = target_state
                self._target_version += 1
                self._cond.notify_all()

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
        while self.lc.state != State.FINALIZED:
            with self._cond:
                target = self._target_state
                version = self._target_version

            state = self.lc.state
            if state == target and state == State.ACTIVE:
                self.lc.run()
                continue

            outcome = reconcile_step(
                self.lc, target, self.backoff_config
            )
            if not outcome.progressed and outcome.retry_delay > 0:
                self._wait_for_target_change(
                    version, timeout=outcome.retry_delay
                )
