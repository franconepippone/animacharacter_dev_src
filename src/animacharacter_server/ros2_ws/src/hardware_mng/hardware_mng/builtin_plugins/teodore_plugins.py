from typing import Dict, Callable, Any
from collections.abc import Iterable

from lifecycle_pkg import FaultContext, RecoveryResult, TransitionResult

from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand

from mcudrivers.head_driver import Axis, HeadMcuDriver


class _BasicLifecycleController(BaseHardwareController):
    def on_activate(self) -> TransitionResult:
        return TransitionResult.SUCCESS

    def on_deactivate(self) -> TransitionResult:
        return TransitionResult.SUCCESS

    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        return RecoveryResult.success(fault.state_from)


class HeadController(_BasicLifecycleController):
    def __init__(self):
        super().__init__("head", flush_freq=30.0)

        self.driver = HeadMcuDriver("COM3", self.logger)

        self.COMMAND_MAP: Dict[int, Callable[[float], Any]] = {
            1 : lambda v: self.driver.write(Axis.EYE_L, v)
        }

        # dinamically subscribes to all ids present in the map
        self.subscribe_to_command_group(self.COMMAND_MAP.keys())


    def on_awake(self) -> TransitionResult:
        return (
            TransitionResult.SUCCESS
            if self.driver.begin()
            else TransitionResult.FAIL_RETRY
        )

    def on_shutdown(self) -> TransitionResult:
        return (
            TransitionResult.SUCCESS
            if self.driver.deinit()
            else TransitionResult.FAIL_RETRY
        )
    
    def control(self, commands: Iterable[MotionCommand]):
        # controls the head hardware

        with self.driver.batch_write():
            for command in commands:
                fn = self.COMMAND_MAP.get(command.id)
                if fn: fn(command.value)
            
        self.driver.flush()


class BodyController(_BasicLifecycleController):
    def __init__(self):
        super().__init__("body", flush_freq=30.0)

    def on_awake(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult: return TransitionResult.SUCCESS
    def control(self, commands: Iterable[MotionCommand]): pass


class LeftArmController(_BasicLifecycleController):
    def __init__(self):
        super().__init__("l-arm", flush_freq=30.0)
    
    def on_awake(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult: return TransitionResult.SUCCESS
    def control(self, commands: Iterable[MotionCommand]): pass


class RightArmController(_BasicLifecycleController):
    def __init__(self):
        super().__init__("r-arm", flush_freq=30.0)

    def on_awake(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult: return TransitionResult.SUCCESS
    def control(self, commands: Iterable[MotionCommand]): pass    