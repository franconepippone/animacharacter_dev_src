import logging
from queue import Queue
from threading import Event

import pytest

from hardware_mng.abstract_hw_controller import (
    BaseHardwareController,
    ControllerError,
    ControllerFatal,
    ControllerWarning,
    MotionCommand,
)
from hardware_mng.hw_controller_state_reconciler import (
    ControllerState,
    HWControllerStateReconciler,
)
from hardware_mng.looper import LoopDescriptor, LoopRequest, Signal
from hardware_mng.signals_definitions import (
    SIG_CONTOLLER_WARNING,
    SIG_CONTROLLER_ERROR,
    SIG_CONTROLLER_FATAL,
    SIG_CONTROLLER_GENERIC_EXCEPTION,
)


class DummyController(BaseHardwareController):
    def __init__(self, *, read_exc=None, control_exc=None, init_exc=None, deinit_exc=None):
        self.read_exc = read_exc
        self.control_exc = control_exc
        self.init_exc = init_exc
        self.deinit_exc = deinit_exc
        super().__init__(name="dummy", flush_freq=10.0)

    def control(self, commands):
        if self.control_exc is not None:
            raise self.control_exc

    def initialize_hw(self):
        if self.init_exc is not None:
            raise self.init_exc
        return True

    def deinitialize_hw(self):
        if self.deinit_exc is not None:
            raise self.deinit_exc
        return True

    def read(self):
        if self.read_exc is not None:
            raise self.read_exc


class DummyLooper:
    def __init__(self):
        self.started = []
        self.paused = []
        self.resumed = []
        self.stopped = []

    def start_loop(self, loop_id, paused=False):
        self.started.append((loop_id, paused))
        return True

    def pause_loop(self, loop_id):
        self.paused.append(loop_id)
        return True

    def resume_loop(self, loop_id):
        self.resumed.append(loop_id)
        return True

    def stop_loop(self, loop_id):
        self.stopped.append(loop_id)
        return True

    def is_paused(self, loop_id):
        return False


@pytest.fixture
def loop_descriptor():
    return LoopDescriptor(
        name="dummy-loop",
        id=1,
        input_queue=Queue(),
        output_queue=Queue(),
        _run=Event(),
        _wait=Event(),
        context=None,
        freq=10.0,
        job=lambda *_: None,
    )


def test_flush_propagates_read_errors_to_signal_callback(loop_descriptor):
    received = []

    def handler(signal):
        received.append(signal)

    controller = DummyController(read_exc=ControllerError(1, "read failed"))
    controller._set_initialized(True)

    request = controller._flush(Queue(), Queue())

    assert isinstance(request, LoopRequest)
    assert request.action == "STOP" or request.action.name == "STOP"
    assert len(received) == 0

    assert request.signal is not None
    assert request.signal.name == SIG_CONTROLLER_ERROR
    assert request.signal.kwargs["code"] == 1
    assert request.signal.kwargs["note"] == "read failed"


def test_flush_propagates_control_errors_to_signal_callback(loop_descriptor):
    controller = DummyController(control_exc=ControllerFatal(2, "control exploded"))
    controller._set_initialized(True)

    request = controller._flush(Queue(), Queue())

    assert isinstance(request, LoopRequest)
    assert request.signal is not None
    assert request.signal.name == SIG_CONTROLLER_FATAL
    assert request.signal.kwargs["code"] == 2
    assert request.signal.kwargs["note"] == "control exploded"


def test_reconciler_propagates_init_error_to_signal_callback(loop_descriptor):
    received = []

    def signal_handler(controller, loop, signal):
        received.append((controller.name, loop.id, signal.name, signal.kwargs))

    controller = DummyController(init_exc=ControllerError(3, "init failed"))
    looper = DummyLooper()
    reconciler = HWControllerStateReconciler(signal_handler, looper, logging.getLogger("test"))
    reconciler.add_controller(loop_descriptor, controller)
    reconciler.set_goal_all(ControllerState.RUNNING)

    reconciler.reconcile()

    assert received == [("dummy", 1, SIG_CONTROLLER_ERROR, {"code": 3, "note": "init failed"})]


def test_reconciler_propagates_deinit_error_to_signal_callback(loop_descriptor):
    received = []

    def signal_handler(controller, loop, signal):
        received.append((controller.name, loop.id, signal.name, signal.kwargs))

    controller = DummyController(deinit_exc=ControllerFatal(4, "deinit exploded"))
    controller._set_initialized(True)
    loop_descriptor._thread = type("DummyThread", (), {"is_alive": lambda self: True})()
    looper = DummyLooper()
    reconciler = HWControllerStateReconciler(signal_handler, looper, logging.getLogger("test"))
    reconciler.add_controller(loop_descriptor, controller)
    reconciler.set_goal_all(ControllerState.UNINITIALIZED)

    reconciler.reconcile()

    assert received == [("dummy", 1, SIG_CONTROLLER_FATAL, {"code": 4, "note": "deinit exploded"})]
