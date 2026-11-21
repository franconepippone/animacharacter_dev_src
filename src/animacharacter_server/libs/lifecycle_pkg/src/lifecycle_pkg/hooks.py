"""Lifecycle hook interface and transition-hook lookup."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from .types import (
    FaultContext,
    RecoveryResult,
    TransitionId,
    TransitionResult,
)


class Lifecyclable(ABC):
    """Abstract interface implemented by lifecycle-managed objects."""

    @abstractmethod
    def on_awake(self) -> TransitionResult:
        """Prepare the object for inactive operation."""
        ...

    @abstractmethod
    def on_activate(self) -> TransitionResult:
        """Activate the object."""
        ...

    @abstractmethod
    def on_deactivate(self) -> TransitionResult:
        """Deactivate the object."""
        ...

    @abstractmethod
    def on_shutdown(self) -> TransitionResult:
        """Finalize and release the object."""
        ...

    @abstractmethod
    def on_run(self) -> TransitionResult:
        """Execute one active runtime tick."""
        ...

    @abstractmethod
    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        """Attempt recovery from the supplied fault context."""
        ...

    def get_hook_from_transition_id(
        self, transition_id: TransitionId
    ) -> Callable[[], TransitionResult]:
        """Return this object's hook for a transition identifier."""
        return get_hook_from_transition_id(self, transition_id)


def get_hook_from_transition_id(
    lifecyclable: Lifecyclable, transition_id: TransitionId
) -> Callable[[], TransitionResult]:
    """Return the bound hook matching a transition identifier."""
    hooks: dict[
        TransitionId, Callable[[], TransitionResult]
    ] = {
        TransitionId.AWAKE: lifecyclable.on_awake,
        TransitionId.SHUTDOWN: lifecyclable.on_shutdown,
        TransitionId.ACTIVATE: lifecyclable.on_activate,
        TransitionId.DEACTIVATE: lifecyclable.on_deactivate,
        TransitionId.RUN: lifecyclable.on_run,
    }
    try:
        return hooks[transition_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported transition_id: {transition_id}") from exc
