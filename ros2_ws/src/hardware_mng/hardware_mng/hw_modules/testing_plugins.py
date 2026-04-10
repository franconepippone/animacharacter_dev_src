from typing import Dict, Callable, Any
from collections.abc import Iterable
from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand

from random import random

class A_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("A", flush_freq=1)
        self.faulty_cnt = 0

    def initialize_hw(self) -> bool: 
        self.faulty_cnt += 1
        return self.faulty_cnt > 5
    
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: Iterable[MotionCommand]): print("controlling A")

class B_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("B", flush_freq=1.0)
    
    def initialize_hw(self) -> bool:
        ok = random() > .5 
        print("initializing B", ok); 
        return ok
    
    def deinitialize_hw(self) -> bool:
        ok = random() > .5 
        print("deinitializing B", ok); 
        return ok
    
    def control(self, commands: Iterable[MotionCommand]): print("controlling B")

class C_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("C", flush_freq=1.0)

    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: Iterable[MotionCommand]): print("controlling C")