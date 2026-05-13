from typing import Dict, Callable, Any
from collections.abc import Iterable, Sized
from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand, HardwareCrash

from random import random, choice


messages = 'hellothere', 'this is a test', 'yes definetly a test', 'hi', 'noway!'

class A_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("A", flush_freq=1)
        self.subscribe_to_command_group([1,2,3])
        self.writer = self.create_databus_writer('topic/A', str, 'none')
        self.writer_state = self.create_databus_writer(
            'A/state/x',
            float,
            0.0
        )

    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: list[MotionCommand]):
        self.writer.write(choice(messages)) 
        print(f"controlling A, got {len(commands)} commands")

    def read(self):
        val = 2.2 # read from hardware
        self.writer_state.write(val)

class B_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("B", flush_freq=1.0)
        self.subscribe_to_command_group([4,5,6])

        self.writer = self.create_databus_writer('topic/B', float, 0.0)
        self.reader = self.create_databus_reader('topic/A', str)
    
    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: list[MotionCommand]): print(f"controlling B, got {len(commands)} commands")
    def read(self):
        msg = self.reader.read()
        print("B ctrl read bus, got", msg)

class C_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("C", flush_freq=1.0)
        self.subscribe_to_command_group([7,8,9])

        self.reader = self.create_databus_reader('topic/A', str)
        
        self.reader2 = self.create_databus_reader('A/state/x', float)

    def initialize_hw(self) -> bool: return True
    def deinitialize_hw(self) -> bool: return True
    def control(self, commands: list[MotionCommand]): print(f"controlling C, got {len(commands)} commands")
    def read(self):
        msg = self.reader2.read()
        print("C ctrl read bus, got", msg)