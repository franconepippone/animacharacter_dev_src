from typing import Dict, Callable, Any
from collections.abc import Iterable, Sized
from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand

from random import random

# simulate failures during init and deinit
def faultytrue(fault_chance: float, msg: str) -> bool:
    ok = random() > fault_chance
    print(msg, ok)
    return ok

class A_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("A", flush_freq=1)
        self.subscribe_to_command_group([1,2,3])
        self.faulty_cnt = 0

    def initialize_hw(self) -> bool: 
        self.faulty_cnt += 1
        return self.faulty_cnt > 5 and faultytrue(0.5, "Initializing A:")
    
    def deinitialize_hw(self) -> bool: return faultytrue(0.5, "Deinitializing A:")
    def control(self, commands: list[MotionCommand]): print(f"controlling A, got {len(commands)} commands")


class B_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("B", flush_freq=1.0)
        self.subscribe_to_command_group([4,5,6])
    
    def initialize_hw(self) -> bool: return faultytrue(0.6, "Initializing B:")
    def deinitialize_hw(self) -> bool: return faultytrue(0.7, "Deinitializing B:")
    def control(self, commands: list[MotionCommand]): print(f"controlling B, got {len(commands)} commands")


class C_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("C", flush_freq=1.0)
        self.subscribe_to_command_group([7,8,9])

    def initialize_hw(self) -> bool: return faultytrue(0.8, "Initializing C:")
    def deinitialize_hw(self) -> bool: return faultytrue(0.2, "Deinitializing C:")
    def control(self, commands: list[MotionCommand]): print(f"controlling C, got {len(commands)} commands")
