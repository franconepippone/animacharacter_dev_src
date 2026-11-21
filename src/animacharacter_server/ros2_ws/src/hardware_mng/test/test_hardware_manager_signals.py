import pytest

from lifecycle_pkg import FaultContext, RecoveryResult, TransitionResult

from hardware_mng.abstract_hw_controller import (
    BaseHardwareController,
    ControllerError,
    MotionCommand,
)
from hardware_mng.databus import Databus
from hardware_mng.plugins_loader import load_controllers


class DummyController(BaseHardwareController):
    def __init__(self, *, control_error=None):
        super().__init__(name="dummy", flush_freq=10.0)
        self.control_error = control_error
        self.calls = []

    def on_awake(self):
        return TransitionResult.SUCCESS

    def on_activate(self):
        return TransitionResult.SUCCESS

    def on_deactivate(self):
        return TransitionResult.SUCCESS

    def on_shutdown(self):
        return TransitionResult.SUCCESS

    def on_recover(self, fault: FaultContext):
        return RecoveryResult.success(fault.state_from)

    def read(self):
        self.calls.append("read")

    def control(self, commands):
        if self.control_error is not None:
            raise self.control_error
        self.calls.append(("control", commands))


def test_on_run_dispatches_config_reads_and_controls(monkeypatch):
    controller = DummyController()
    controller.subscribe_to_config_path(
        "device/options",
        lambda value: controller.calls.append(("config", value)),
    )
    controller.enqueue_config_update(
        {"device": {"options": {"enabled": True}}}
    )
    command = MotionCommand(7, 0.5)
    controller.enqueue_command(command)
    sleeps = []
    monkeypatch.setattr(
        "hardware_mng.abstract_hw_controller.time.sleep", sleeps.append
    )

    assert controller.on_run() == TransitionResult.SUCCESS

    assert controller.calls == [
        ("config", {"enabled": True}),
        "read",
        ("control", [command]),
    ]
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= 0.1


def test_on_run_propagates_hook_errors_for_lifecycle_recovery():
    controller = DummyController(control_error=RuntimeError("controller failed"))

    with pytest.raises(RuntimeError, match="controller failed"):
        controller.on_run()


def test_controller_specific_exceptions_are_deprecated():
    with pytest.warns(DeprecationWarning, match="deprecated"):
        ControllerError(1, "legacy exception")


def test_plugin_loader_loads_valid_controller_classes():
    databus = Databus()
    controllers, issues = load_controllers(
        [
            "hardware_mng.builtin_plugins.testing_databus:A_Controller",
            "hardware_mng.builtin_plugins.testing_databus:B_Controller",
            "hardware_mng.builtin_plugins.testing_databus:C_Controller",
        ],
        [],
        databus,
    )

    assert [controller.name for controller in controllers] == ["A", "B", "C"]
    assert issues == []
    databus.finalize()


def test_plugin_loader_reports_bad_paths_without_stopping_loading():
    databus = Databus()
    controllers, issues = load_controllers(
        [
            "missing_module:MissingController",
            "hardware_mng.builtin_plugins.testing_databus:A_Controller",
        ],
        [],
        databus,
    )

    assert [controller.name for controller in controllers] == ["A"]
    assert len(issues) == 1
    assert issues[0].source == "missing_module:MissingController"
