from __future__ import annotations

import pytest

from lifecycle_pkg import (
    BackoffConfig,
    LifecyclableWrapper,
    RecoveryResult,
    State,
    TransitionResult
)
from lifecycle_pkg.reconcile import reconcile_step
from tests.conftest import RecordedDevice


def test_backoff_config_validation() -> None:
    with pytest.raises(ValueError):
        BackoffConfig(retry_base_delay=-0.1)
    with pytest.raises(ValueError):
        BackoffConfig(retry_multiplier=0.5)
    with pytest.raises(ValueError):
        BackoffConfig(recover_max_delay=-1.0)


def test_backoff_delay_calculations() -> None:
    cfg = BackoffConfig(
        retry_base_delay=0.1,
        retry_multiplier=2.0,
        retry_max_delay=0.35,
        recover_base_delay=0.2,
        recover_multiplier=3.0,
        recover_max_delay=1.0,
    )
    assert cfg.retry_delay_for(1) == pytest.approx(0.1)
    assert cfg.retry_delay_for(2) == pytest.approx(0.2)
    assert cfg.retry_delay_for(3) == pytest.approx(0.35)  # capped at max_delay

    assert cfg.recover_delay_for(1) == pytest.approx(0.2)
    assert cfg.recover_delay_for(2) == pytest.approx(0.6)
    assert cfg.recover_delay_for(3) == pytest.approx(1.0)  # capped at max_delay


def test_reconcile_step_advances_one_transition_at_a_time(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    # From UNCONFIGURED toward ACTIVE, first step is AWAKE -> INACTIVE
    outcome = reconcile_step(wrapper, State.ACTIVE)
    assert outcome.progressed is True
    assert outcome.retry_delay == 0.0
    assert wrapper.state == State.INACTIVE
    assert device.events == ["awake"]

    # Already at target state -> no progress, zero delay
    idle = reconcile_step(wrapper, State.INACTIVE)
    assert idle.progressed is False
    assert idle.retry_delay == 0.0


def test_reconcile_step_applies_configured_retry_and_recovery_backoffs(
    wrapper: LifecyclableWrapper, device: RecordedDevice
) -> None:
    cfg = BackoffConfig(
        retry_base_delay=0.05,
        retry_multiplier=2.0,
        retry_max_delay=0.5,
        recover_base_delay=0.1,
        recover_multiplier=2.0,
        recover_max_delay=0.8,
        fault_entry_delay=0.25,
    )
    device.awake_results = [TransitionResult.FAIL_RETRY]

    out_retry = reconcile_step(wrapper, State.INACTIVE, backoff=cfg)
    assert out_retry.progressed is False
    assert out_retry.retry_delay == pytest.approx(0.05)

    # Fault entry uses fault_entry_delay
    device.awake_results = [RuntimeError("hardware error")]
    out_fault = reconcile_step(wrapper, State.INACTIVE, backoff=cfg)
    assert out_fault.progressed is False
    assert out_fault.retry_delay == pytest.approx(0.25)
    assert wrapper.state == State.FAULTED

    # Failed recovery uses recover_delay_for(attempt)
    device.recover_results = [RecoveryResult.failed(), RecoveryResult.failed()]
    out_rec1 = reconcile_step(wrapper, State.INACTIVE, backoff=cfg)
    assert out_rec1.progressed is False
    assert out_rec1.retry_delay == pytest.approx(0.1)

    out_rec2 = reconcile_step(wrapper, State.INACTIVE, backoff=cfg)
    assert out_rec2.progressed is False
    assert out_rec2.retry_delay == pytest.approx(0.2)

    # Successful recovery advances state
    device.recover_results = [RecoveryResult.success(State.INACTIVE)]
    out_rec3 = reconcile_step(wrapper, State.INACTIVE, backoff=cfg)
    assert out_rec3.progressed is True
    assert out_rec3.retry_delay == 0.0
    assert wrapper.state == State.INACTIVE


def test_reconcile_step_rejects_unreachable_target(
    wrapper: LifecyclableWrapper,
) -> None:
    wrapper.state = State.INACTIVE
    with pytest.raises(ValueError):
        reconcile_step(wrapper, State.UNCONFIGURED)