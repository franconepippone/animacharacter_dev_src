"""Routing tables and target-state validation for lifecycle transitions."""

from __future__ import annotations

from collections import deque
from types import MappingProxyType
from typing import Mapping

from .types import State, TransitionId


TRANSITION_MAP: dict[TransitionId, tuple[State, State]] = {
    TransitionId.AWAKE: (State.UNCONFIGURED, State.INACTIVE),
    TransitionId.SHUTDOWN: (State.INACTIVE, State.FINALIZED),
    TransitionId.ACTIVATE: (State.INACTIVE, State.ACTIVE),
    TransitionId.DEACTIVATE: (State.ACTIVE, State.INACTIVE),
    TransitionId.RUN: (State.ACTIVE, State.ACTIVE),
}

VALID_TARGET_STATES: frozenset[State] = frozenset(
    state for state in State if state != State.FAULTED
)


def _build_next_transition_map() -> Mapping[
    tuple[State, State], TransitionId
]:
    """Precompute the first transition for each reachable state pair."""
    routes: dict[tuple[State, State], TransitionId] = {}

    for start in State:
        if start == State.FAULTED:
            continue

        queue: deque[tuple[State, TransitionId | None]] = deque([(start, None)])
        visited: set[State] = {start}

        while queue:
            current, first_transition = queue.popleft()
            for transition_id, (source, destination) in TRANSITION_MAP.items():
                if source != current or destination == State.FAULTED:
                    continue
                next_first = transition_id if first_transition is None else first_transition
                if destination not in visited:
                    visited.add(destination)
                    routes[(start, destination)] = next_first
                    queue.append((destination, next_first))

    return MappingProxyType(routes)


NEXT_TRANSITION_MAP: Mapping[
    tuple[State, State], TransitionId
] = _build_next_transition_map()


def _validate_target_state(target_state: State) -> None:
    """Reject faulted and unknown target states."""
    if not isinstance(target_state, State) or target_state == State.FAULTED:
        raise ValueError(f"Invalid target state: {target_state}")
    if target_state not in VALID_TARGET_STATES:
        raise ValueError(f"Invalid target state: {target_state}")


def _validate_reachable_target(
    current_state: State, target_state: State
) -> None:
    """Validate that a target is reachable from the current state."""
    _validate_target_state(target_state)
    if not isinstance(current_state, State):
        raise ValueError(f"Invalid current state: {current_state}")
    if current_state == State.FAULTED or current_state == target_state:
        return
    if (current_state, target_state) not in NEXT_TRANSITION_MAP:
        raise ValueError(
            f"Target state {target_state} is unreachable from {current_state}"
        )
