"""Core lifecycle types and immutable fault/recovery records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class State(Enum):
    """States in the component lifecycle."""

    UNCONFIGURED = auto()
    INACTIVE = auto()
    ACTIVE = auto()
    FINALIZED = auto()
    FAULTED = auto()


class TransitionId(Enum):
    """Identifiers for lifecycle transitions and runtime ticks."""

    AWAKE = auto()
    SHUTDOWN = auto()
    ACTIVATE = auto()
    DEACTIVATE = auto()
    RUN = auto()


class TransitionResult(Enum):
    """Outcome returned by a lifecycle or runtime hook."""

    SUCCESS = auto()
    FAIL_RETRY = auto()
    ERROR = auto()


class RecoveryResultStatus(Enum):
    """Outcome returned by a recovery hook."""

    SUCCESS = auto()
    FAIL = auto()


@dataclass(frozen=True)
class RecoveryResult:
    """Immutable result of a recovery attempt."""

    status: RecoveryResultStatus
    new_state: State | None = None

    @staticmethod
    def failed() -> "RecoveryResult":
        """Create a failed recovery result."""
        return RecoveryResult(RecoveryResultStatus.FAIL, None)

    @staticmethod
    def success(new_state: State) -> "RecoveryResult":
        """Create a successful recovery result for a valid new state."""
        return RecoveryResult(RecoveryResultStatus.SUCCESS, new_state)


@dataclass(frozen=True)
class FaultContext:
    """Immutable metadata describing a faulted operation."""

    transition_id: TransitionId
    attempt_n: int
    exception: Exception | None

    @property
    def state_from(self) -> State:
        """State from which the faulted transition originated."""
        routes = {
            TransitionId.AWAKE: State.UNCONFIGURED,
            TransitionId.SHUTDOWN: State.INACTIVE,
            TransitionId.ACTIVATE: State.INACTIVE,
            TransitionId.DEACTIVATE: State.ACTIVE,
            TransitionId.RUN: State.ACTIVE,
        }
        return routes[self.transition_id]

    @property
    def state_to(self) -> State:
        """Destination state intended by the faulted transition."""
        routes = {
            TransitionId.AWAKE: State.INACTIVE,
            TransitionId.SHUTDOWN: State.FINALIZED,
            TransitionId.ACTIVATE: State.ACTIVE,
            TransitionId.DEACTIVATE: State.INACTIVE,
            TransitionId.RUN: State.ACTIVE,
        }
        return routes[self.transition_id]
