import threading
import time
from typing import cast
from unittest.mock import Mock, patch

from hardware_mng.controller_manager import ControllerManager
from lifecycle_pkg import LifecycleThreadedRunner
from lifecycle_pkg.events import State as ControllerState
from rclpy.logging import RcutilsLogger


class UnreconciledRunner:

    def __init__(self, reject_target: bool = False) -> None:
        self.reject_target = reject_target
        self.live_state = ControllerState.INACTIVE
        self.target_state = ControllerState.INACTIVE
        self.thread_name = 'lifecycle-test'

    def set_target_state(self, state: ControllerState) -> None:
        if self.reject_target:
            raise ValueError('target rejected')
        self.target_state = state

    def get_live_state(self) -> ControllerState:
        return self.live_state

    def get_target_state(self) -> ControllerState:
        return self.target_state

    def join(self, timeout: float) -> bool:
        return True

    def is_alive(self) -> bool:
        return False


def _manager_with_runner(
    runner: UnreconciledRunner,
) -> tuple[ControllerManager, Mock]:
    manager = object.__new__(ControllerManager)
    manager._controller_lock = threading.RLock()
    manager._operation_timeout = 0.01
    logger = Mock()
    manager._logger = cast(RcutilsLogger, logger)
    manager._controller_runners = [
        cast(LifecycleThreadedRunner, runner)
    ]
    manager._runners_by_name = {'test': manager._controller_runners[0]}
    manager._is_active = False
    return manager, logger


def test_activate_succeeds_and_warns_when_target_does_not_reconcile():
    manager, logger = _manager_with_runner(UnreconciledRunner())

    with patch(
        'hardware_mng.controller_manager.time.sleep', wraps=time.sleep
    ) as sleep:
        assert manager.activate()

    assert manager._is_active
    sleep.assert_called()
    logger.warning.assert_called_once()
    assert 'live=INACTIVE, target=ACTIVE' in logger.warning.call_args.args[0]


def test_activate_fails_when_controller_rejects_target():
    manager, logger = _manager_with_runner(
        UnreconciledRunner(reject_target=True)
    )

    assert not manager.activate()
    assert not manager._is_active
    logger.warning.assert_not_called()
    logger.error.assert_called_once()


def test_cleanup_succeeds_and_warns_when_runner_does_not_finalize():
    runner = UnreconciledRunner()
    manager, logger = _manager_with_runner(runner)
    manager.controllers = []

    assert manager.cleanup()
    assert runner.target_state == ControllerState.FINALIZED
    logger.warning.assert_called_once()
    assert (
        'live=INACTIVE, target=FINALIZED'
        in logger.warning.call_args.args[0]
    )
