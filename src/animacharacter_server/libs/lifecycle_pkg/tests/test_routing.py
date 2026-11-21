from __future__ import annotations

import pytest

from lifecycle_pkg import (
    NEXT_TRANSITION_MAP,
    State,
    TransitionId,
    VALID_TARGET_STATES,
)
from lifecycle_pkg.routing import _validate_reachable_target, _validate_target_state


def test_faulted_not_in_valid_target_states() -> None:
    assert State.FAULTED not in VALID_TARGET_STATES
    with pytest.raises(ValueError):
        _validate_target_state(State.FAULTED)


def test_multi_hop_routing_from_unconfigured_to_finalized() -> None:
    assert NEXT_TRANSITION_MAP[(State.UNCONFIGURED, State.FINALIZED)] == TransitionId.AWAKE
    assert NEXT_TRANSITION_MAP[(State.INACTIVE, State.FINALIZED)] == TransitionId.SHUTDOWN


def test_multi_hop_routing_from_active_to_finalized() -> None:
    assert NEXT_TRANSITION_MAP[(State.ACTIVE, State.FINALIZED)] == TransitionId.DEACTIVATE
    assert NEXT_TRANSITION_MAP[(State.ACTIVE, State.INACTIVE)] == TransitionId.DEACTIVATE


def test_unreachable_target_raises_value_error() -> None:
    # Cannot go backwards from INACTIVE to UNCONFIGURED or from FINALIZED to ACTIVE
    assert (State.INACTIVE, State.UNCONFIGURED) not in NEXT_TRANSITION_MAP
    assert (State.FINALIZED, State.ACTIVE) not in NEXT_TRANSITION_MAP

    with pytest.raises(ValueError):
        _validate_reachable_target(State.INACTIVE, State.UNCONFIGURED)

    with pytest.raises(ValueError):
        _validate_reachable_target(State.FINALIZED, State.ACTIVE)


def test_faulted_current_state_allows_valid_target_states() -> None:
    # Recovery can return to any valid non-faulted target state
    _validate_reachable_target(State.FAULTED, State.UNCONFIGURED)
    _validate_reachable_target(State.FAULTED, State.INACTIVE)
    _validate_reachable_target(State.FAULTED, State.ACTIVE)
    _validate_reachable_target(State.FAULTED, State.FINALIZED)

    with pytest.raises(ValueError):
        _validate_reachable_target(State.FAULTED, State.FAULTED)


def test_routing_map_is_read_only() -> None:
    with pytest.raises(TypeError):
        NEXT_TRANSITION_MAP[(State.INACTIVE, State.ACTIVE)] = TransitionId.SHUTDOWN  # type: ignore[index]