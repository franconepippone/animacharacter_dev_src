from collections.abc import Iterable, Sequence
from typing import NamedTuple

from rclpy.logging import RcutilsLogger
from dataclasses import dataclass
from abc import ABC, abstractmethod
from queue import Queue, Empty

from click import command

# a "motion frame" is a set of motion commands
class MotionCommand(NamedTuple):
    id: int
    value: float

class BaseHardwareController(ABC):
    """
    A Hardware Controller or Module is responsible for the execution of motion commands. Hardware controller
    are highly coupled to hardware and might differ from robot to robot. A single robot might use multiple hardware controllers.
    A Hardware Controller "subscribes" to a set of motion command ids (command_group set, passed in __init__ or via "subscribe_to_command_group"). All the recevied commands witch matching ids will be
    passed to the "control" method of the subscribed hardware controllers at a frequency specified by flush_frequency. The control method handles updating the
    hardware with the received motion commands values. 

    Based on hardware implementation, the "control" method could either directly update hardware command per command, or could batch all updates in one hardware
    update communication (ideal solution). In any case, implementation of "control" is completely up to the user, but must always take less than a loop period to ensure 
    a constant update frequency.

    Hardware controllers are dynamically loaded as a plugins by the hardware manager system. A Hardware Configuration is a set of hardware controllers that are loaded and used
    by the hardware manager system. A Configuration can be registered in the "hw_configurations.yaml" file, and then used by passing it as an argument when launching
    the hardware manager system.
    """
    
    def __init__(self, name: str, flush_freq: float, command_group: set[int] = set()) -> None:
        self.name = name
        self.flush_freq = flush_freq # flush frequency in Hz
        self.command_group = command_group

        if self.flush_freq <= 0:
            raise ValueError(f"flush_freq must be positive, got {self.flush_freq}")

        self.logger = RcutilsLogger(f"HWController-{self.name}")

    def subscribe_to_command_group(self, ids_group: Iterable[int]):
        """If not set during __init__, use this to subscribe to a set of motion """
        self.command_group = set(ids_group)

    # this is used as the "job" of the looper
    def _flush(self, incoming_commands: Queue[MotionCommand], _outgoing_commands: Queue[MotionCommand]):
            commands = []
            # use for and not while, so we only process a finite set of commands (avoid infinite loop if commands are received faster than consumed)
            for _ in range(incoming_commands.qsize()):
                try:
                    command = incoming_commands.get_nowait()
                    commands.append(command)
                except Empty:
                    continue

            self.control(commands)

    @abstractmethod
    def control(self, commands: Iterable[MotionCommand]):
        """Implement your custom control logic for a set of motion commands."""
    
    @abstractmethod
    def initialize_hw(self) -> bool:
        """Puts the hardware in a ready-to-operate state. Returns True on success."""

    @abstractmethod
    def deinitialize_hw(self) -> bool:
        """Puts the hardware at rest. Hardware should be re-initializable after this."""