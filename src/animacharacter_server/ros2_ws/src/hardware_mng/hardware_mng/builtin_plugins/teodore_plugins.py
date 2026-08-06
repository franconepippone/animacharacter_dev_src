from typing import Dict, Callable, Any
from collections.abc import Iterable
from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand

from mcudrivers.head_driver import Axis, HeadMcuDriver


class HeadController(BaseHardwareController):
    def __init__(self):
        super().__init__("head", flush_freq=30.0)

        # helper class to drive the hardware
        self.driver = HeadMcuDriver("COM3", self.logger)

        self.COMMAND_MAP: Dict[int, Callable[[float], Any]] = {
            1 : lambda v: self.driver.write(Axis.EYE_L, v)
        }

        # dinamically subscribes to all ids present in the map
        self.subscribe_to_command_group(self.COMMAND_MAP.keys())


    def initialize_hw(self) -> bool:
        return self.driver.begin()

    def deinitialize_hw(self) -> bool:
        return self.driver.deinit()
    
    def control(self, commands: Iterable[MotionCommand]):
        # controls the head hardware

        with self.driver.batch_write():
            for command in commands:
                fn = self.COMMAND_MAP.get(command.id)
                if fn: fn(command.value)
            
        self.driver.flush()


class BodyController(BaseHardwareController):
    def __init__(self):
        super().__init__("body", flush_freq=30.0)

    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: Iterable[MotionCommand]): pass

class LeftArmController(BaseHardwareController):
    def __init__(self):
        super().__init__("l-arm", flush_freq=30.0)
    
    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: Iterable[MotionCommand]): pass

class RightArmController(BaseHardwareController):
    def __init__(self):
        super().__init__("r-arm", flush_freq=30.0)

    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: Iterable[MotionCommand]): pass    