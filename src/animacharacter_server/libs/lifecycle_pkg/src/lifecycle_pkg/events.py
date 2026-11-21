from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
import time
from typing import Iterable, Protocol, runtime_checkable

from .types import RecoveryResultStatus, State, TransitionId, TransitionResult


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class LifecycleEvent:
    """Base event emitted by the lifecycle runner and state machine."""

    timestamp: float = field(default_factory=time.monotonic)
    level: LogLevel = LogLevel.INFO
    message: str = ""


@dataclass(frozen=True)
class LogEvent(LifecycleEvent):
    """General diagnostic log message."""

    context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetStateChangedEvent(LifecycleEvent):
    """Emitted when the desired target is initialized or changed."""

    previous_target: State | None = None
    new_target: State = State.UNCONFIGURED


@dataclass(frozen=True)
class TransitionCompletedEvent(LifecycleEvent):
    """Emitted after a lifecycle transition hook finishes."""

    transition_id: TransitionId = TransitionId.AWAKE
    state_from: State = State.UNCONFIGURED
    state_to: State = State.UNCONFIGURED
    result: TransitionResult = TransitionResult.SUCCESS
    exception: Exception | None = None


@dataclass(frozen=True)
class FaultEnteredEvent(LifecycleEvent):
    """Emitted when the wrapper enters State.FAULTED."""

    transition_id: TransitionId = TransitionId.RUN
    exception: Exception | None = None


@dataclass(frozen=True)
class RecoveryAttemptEvent(LifecycleEvent):
    """Emitted after an on_recover attempt runs."""

    attempt_n: int = 1
    status: RecoveryResultStatus = RecoveryResultStatus.FAIL
    new_state: State | None = None
    exception: Exception | None = None


@dataclass(frozen=True)
class RunnerExitedEvent(LifecycleEvent):
    """Emitted when the lifecycle runner exits."""

    final_state: State = State.UNCONFIGURED


@runtime_checkable
class EventSink(Protocol):
    """Non-blocking sink called synchronously by the lifecycle runner."""

    def emit(self, event: LifecycleEvent) -> None:
        """Consume an event quickly without blocking lifecycle work."""
        ...


class NullEventSink:
    """Discard lifecycle events."""

    def emit(self, event: LifecycleEvent) -> None:
        """Ignore an event."""


class StdlibLoggingSink:
    """Forward lifecycle events to a standard-library logger."""

    _LEVELS = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
    }

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = (
            logger if logger is not None else logging.getLogger("lifecycle_pkg")
        )

    def emit(self, event: LifecycleEvent) -> None:
        """Log an event and attach it to the resulting LogRecord."""
        message = event.message or type(event).__name__
        self._logger.log(
            self._LEVELS[event.level],
            message,
            extra={"lifecycle_event": event},
        )


class FanOutEventSink:
    """Forward each event to multiple sinks."""

    def __init__(self, sinks: Iterable[EventSink]) -> None:
        self._sinks = tuple(sinks)
        self._logger = logging.getLogger("lifecycle_pkg.events")

    def emit(self, event: LifecycleEvent) -> None:
        """Forward to every sink, isolating individual sink failures."""
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception:
                self._logger.exception(
                    "Lifecycle event sink %r failed", sink
                )