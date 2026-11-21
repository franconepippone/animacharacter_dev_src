from __future__ import annotations

import pytest

from lifecycle_pkg import (
    LifecyclableWrapper,
    RecoveryResult,
    RecoveryResultStatus,
    State,
    TransitionId,
    TransitionResult,
)
from tests.conftest import RecordedDevice


def test_happy_path_transitions_and_run(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    assert wrapper.state == State.UNCONFIGURED

    assert wrapper.transition(TransitionId.AWAKE) == TransitionResult.SUCCESS
    assert wrapper.state == State.INACTIVE

    assert wrapper.transition(TransitionId.ACTIVATE) == TransitionResult.SUCCESS
    assert wrapper.state == State.ACTIVE

    assert wrapper.run() == TransitionResult.SUCCESS
    assert wrapper.state == State.ACTIVE

    assert wrapper.transition(TransitionId.DEACTIVATE) == TransitionResult.SUCCESS
    assert wrapper.state == State.INACTIVE

    assert wrapper.transition(TransitionId.SHUTDOWN) == TransitionResult.SUCCESS
    assert wrapper.state == State.FINALIZED

    assert device.events == ["awake", "activate", "run", "deactivate", "shutdown"]


def test_invalid_transition_from_current_state_raises(
    wrapper: LifecyclableWrapper,
) -> None:
    # Cannot ACTIVATE while still UNCONFIGURED
    with pytest.raises(ValueError):
        wrapper.transition(TransitionId.ACTIVATE)


def test_run_outside_active_state_raises(wrapper: LifecyclableWrapper) -> None:
    with pytest.raises(RuntimeError):
        wrapper.run()


def test_fail_retry_keeps_current_state_and_does_not_fault(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    device.awake_results = [TransitionResult.FAIL_RETRY, TransitionResult.SUCCESS]

    res1 = wrapper.transition(TransitionId.AWAKE)
    assert res1 == TransitionResult.FAIL_RETRY
    assert wrapper.state == State.UNCONFIGURED
    assert wrapper.current_fault is None

    res2 = wrapper.transition(TransitionId.AWAKE)
    assert res2 == TransitionResult.SUCCESS
    assert wrapper.state == State.INACTIVE


def test_transition_exception_enters_faulted_and_recovers(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    boom = RuntimeError("serial port disconnected")
    device.activate_results = [boom]
    device.recover_results = [
        RecoveryResult.failed(),
        RecoveryResult.success(State.INACTIVE),
    ]

    wrapper.transition(TransitionId.AWAKE)
    res = wrapper.transition(TransitionId.ACTIVATE)

    assert res == TransitionResult.ERROR
    assert wrapper.state == State.FAULTED
    assert wrapper.current_fault is not None
    assert wrapper.current_fault.transition_id == TransitionId.ACTIVATE
    assert wrapper.current_fault.exception is boom

    # First recovery attempt fails -> remains FAULTED, attempt_n == 1
    rec1 = wrapper.run_recover()
    assert rec1.status == RecoveryResultStatus.FAIL
    assert wrapper.state == State.FAULTED
    assert device.recover_contexts[0].attempt_n == 1
    assert device.recover_contexts[0].state_from == State.INACTIVE
    assert device.recover_contexts[0].state_to == State.ACTIVE

    # Second recovery attempt succeeds -> moves to INACTIVE and clears fault
    rec2 = wrapper.run_recover()
    assert rec2.status == RecoveryResultStatus.SUCCESS
    assert rec2.new_state == State.INACTIVE
    assert wrapper.state == State.INACTIVE
    assert wrapper.current_fault is None
    assert device.recover_contexts[1].attempt_n == 2


def test_run_error_enters_faulted(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    device.run_results = [TransitionResult.ERROR]
    wrapper.transition(TransitionId.AWAKE)
    wrapper.transition(TransitionId.ACTIVATE)

    res = wrapper.run()
    assert res == TransitionResult.ERROR
    assert wrapper.state == State.FAULTED
    assert wrapper.current_fault is not None
    assert wrapper.current_fault.transition_id == TransitionId.RUN


def test_recovery_to_faulted_or_none_raises(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    device.awake_results = [RuntimeError("bad awake")]
    device.recover_results = [RecoveryResult(RecoveryResultStatus.SUCCESS, State.FAULTED)]
    wrapper.transition(TransitionId.AWAKE)

    with pytest.raises(ValueError):
        wrapper.run_recover()