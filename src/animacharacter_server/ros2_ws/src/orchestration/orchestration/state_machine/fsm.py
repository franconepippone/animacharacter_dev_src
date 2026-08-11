from __future__ import annotations

from enum import Enum, auto
from typing import Generic, TypeVar
from dataclasses import dataclass



S = TypeVar("S", bound=Enum)


@dataclass(slots=True, frozen=True)
class StateChangeResult(Generic[S]):
    """Result of a state change in the system FSM."""
    prev_state: S
    new_state: S
    legal_transition: bool

    @property
    def changed(self) -> bool:
        """Returns True if the state has changed, False otherwise."""
        return self.prev_state != self.new_state


class FSM(Generic[S]):
    """A simple finite state machine that validates state transitions.

    The FSM does not handle events or actions. External code decides when a
    transition should happen, and the FSM only verifies that the transition
    is allowed.
    """

    def __init__(self, initial_state: S) -> None:
        """Create an FSM with the given initial state."""
        self._state: S = initial_state
        self._transitions: dict[S, set[S]] = {}
        self._finalized: bool = False

    @property
    def state(self) -> S:
        """Return the current state."""
        return self._state

    def add_transition(self, source: S, destination: S) -> None:
        """Add a valid transition from one state to another.

        Raises:
            RuntimeError: If the FSM has already been finalized.
        """
        self._ensure_mutable()
        self._transitions.setdefault(source, set()).add(destination)

    def add_transitions(self, source: S, destinations: set[S]) -> None:
        """Add multiple valid transitions from a single source state.

        Raises:
            RuntimeError: If the FSM has already been finalized.
        """
        self._ensure_mutable()
        self._transitions.setdefault(source, set()).update(destinations)

    def finalize(self) -> None:
        """Freeze the FSM configuration.

        After finalization, no new transitions can be added.
        """
        self._ensure_mutable()
        self._finalized = True

    def change_state(self, new_state: S) -> StateChangeResult[S]:
        """Change the current state if the transition is valid. Returns a state
        change transition object.

        Raises:
            ValueError: If the requested transition is not allowed.
        """
        allowed = self._transitions.get(self._state, set())

        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self._state.name} -> {new_state.name}"
            )

        prev_state = self._state
        self._state = new_state
        return StateChangeResult(prev_state, new_state, True)

    def force_change_state(self, new_state: S) -> StateChangeResult[S]:
        """Forcefully change state independent of the transition rules. Return 
        state change result object.
        
        This always transitions."""

        try:
            return self.change_state(new_state)
        except ValueError:
            prev_state = self._state
            self._state = new_state
            return StateChangeResult(prev_state, new_state, False)

    def _ensure_mutable(self) -> None:
        """Raise an error if the FSM configuration is finalized."""
        if self._finalized:
            raise RuntimeError("FSM has been finalized.")






if __name__ == "__main__":
    class TestState(Enum):
        """Testing State of the engine"""

        IDLE = auto()
        RUNNING = auto()
        PAUSED = auto()



    fsm = FSM(TestState.IDLE)

    fsm.add_transition(TestState.IDLE, TestState.RUNNING)
    fsm.add_transitions(
        TestState.RUNNING,
        {TestState.IDLE, TestState.PAUSED}
    )
    fsm.add_transition(TestState.PAUSED, TestState.RUNNING)

    fsm.finalize()

    fsm.change_state(TestState.RUNNING)
    fsm.change_state(TestState.PAUSED)
    fsm.change_state(TestState.IDLE)  # ValueError