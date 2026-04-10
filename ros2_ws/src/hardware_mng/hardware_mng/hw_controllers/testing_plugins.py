from typing import Dict, Callable, Any
from collections.abc import Iterable
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
        self.faulty_cnt = 0

    def initialize_hw(self) -> bool: 
        self.faulty_cnt += 1
        return self.faulty_cnt > 5 and faultytrue(0.5, "Initializing A:")
    
    def deinitialize_hw(self) -> bool: return faultytrue(0.5, "Deinitializing A:")
    def control(self, commands: Iterable[MotionCommand]): print("controlling A")

class B_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("B", flush_freq=1.0)
    
    def initialize_hw(self) -> bool: return faultytrue(0.6, "Initializing B:")
    def deinitialize_hw(self) -> bool: return faultytrue(0.7, "Deinitializing B:")
    def control(self, commands: Iterable[MotionCommand]): print("controlling B")

class C_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("C", flush_freq=1.0)

    def initialize_hw(self) -> bool: return faultytrue(0.8, "Initializing C:")
    def deinitialize_hw(self) -> bool: return faultytrue(0.2, "Deinitializing C:")
    def control(self, commands: Iterable[MotionCommand]): print("controlling C")
