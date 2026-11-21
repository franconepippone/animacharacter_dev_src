from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest

from lifecycle_pkg import (
    FaultContext,
    Lifecyclable,
    LifecyclableWrapper,
    RecoveryResult,
    State,
    TransitionId,
    TransitionResult,
)


@dataclass
class RecordedDevice(Lifecyclable):
    """Configurable test double recording lifecycle hook calls and outcomes."""

    events: list[str] = field(default_factory=list)
    awake_results: list[TransitionResult | Exception] = field(default_factory=list)
    activate_results: list[TransitionResult | Exception] = field(default_factory=list)
    deactivate_results: list[TransitionResult | Exception] = field(default_factory=list)
    shutdown_results: list[TransitionResult | Exception] = field(default_factory=list)
    run_results: list[TransitionResult | Exception] = field(default_factory=list)
    recover_results: list[RecoveryResult | Exception] = field(default_factory=list)
    recover_contexts: list[FaultContext] = field(default_factory=list)

    # Optional synchronization hooks for multi-threaded runner tests
    on_run_started: threading.Event | None = None
    allow_run_tick: threading.Event | None = None
    max_run_ticks: int | None = None
    run_ticks_executed: int = 0

    @staticmethod
    def _pop_or_default(
        queue: list[TransitionResult | Exception],
        default: TransitionResult,
    ) -> TransitionResult:
        if not queue:
            return default
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def on_awake(self) -> TransitionResult:
        self.events.append("awake")
        return self._pop_or_default(self.awake_results, TransitionResult.SUCCESS)

    def on_activate(self) -> TransitionResult:
        self.events.append("activate")
        return self._pop_or_default(self.activate_results, TransitionResult.SUCCESS)

    def on_deactivate(self) -> TransitionResult:
        self.events.append("deactivate")
        return self._pop_or_default(self.deactivate_results, TransitionResult.SUCCESS)

    def on_shutdown(self) -> TransitionResult:
        self.events.append("shutdown")
        return self._pop_or_default(self.shutdown_results, TransitionResult.SUCCESS)

    def on_run(self) -> TransitionResult:
        self.events.append("run")
        self.run_ticks_executed += 1
        if self.on_run_started is not None:
            self.on_run_started.set()
        if self.allow_run_tick is not None:
            self.allow_run_tick.wait(timeout=1.0)
            self.allow_run_tick.clear()
        if self.max_run_ticks is not None and self.run_ticks_executed >= self.max_run_ticks:
            return TransitionResult.SUCCESS
        return self._pop_or_default(self.run_results, TransitionResult.SUCCESS)

    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        self.events.append(f"recover:{fault.transition_id.name}:{fault.attempt_n}")
        self.recover_contexts.append(fault)
        if not self.recover_results:
            return RecoveryResult.success(State.INACTIVE)
        item = self.recover_results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def device() -> RecordedDevice:
    return RecordedDevice()


@pytest.fixture
def wrapper(device: RecordedDevice) -> LifecyclableWrapper:
    return LifecyclableWrapper(device)