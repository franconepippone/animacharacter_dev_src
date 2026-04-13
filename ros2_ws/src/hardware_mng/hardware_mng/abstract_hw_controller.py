from collections.abc import Iterable, Callable
from typing import NamedTuple

from rclpy.logging import RcutilsLogger
from abc import ABC, abstractmethod
from queue import Queue, Empty


class HardwareCrash(Exception):
    """
    Raise this in `read` or `control` if the hardware becomes unresponsive and you want to trigger a reset.
    This internally will reset the controller to an uninitialized state and will allow the Hardware Manager to try to re-initialize it automatically.
    """
    pass

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
        self._initialized = False

        if self.flush_freq <= 0:
            raise ValueError(f"flush_freq must be positive, got {self.flush_freq}")

        self.logger = RcutilsLogger(f"HWController-{self.name}")
        self._setup_wrappers()

    def subscribe_to_command_group(self, ids_group: Iterable[int]):
        """If not set during __init__, use this to subscribe to a set of motion commands"""
        self.command_group = set(ids_group)

    # this is used as the "job" of the looper
    def _flush(self, incoming_commands: Queue[MotionCommand], _outgoing_commands: Queue[MotionCommand]):
            
            if not self.is_initialized(): return # prevent flush if not initialized

            commands = []
            # use for and not while, so we only process a finite set of commands (avoid infinite loop if commands are received faster than consumed)
            for _ in range(incoming_commands.qsize()):
                try:
                    command = incoming_commands.get_nowait()
                    commands.append(command)
                except Empty:
                    continue
            try:
                self.read() # first poll for any data
                self.control(commands) # then write command instructions
            except HardwareCrash as e:
                self._set_initialized(False)
                self.logger.error(f"Hardware crash in controller '{self.name}': {e}")
            except Exception as e:
                # we interpret an exception as an hardware failure and reset the state to uninitialized
                self._set_initialized(False)
                self.logger.error(f"Unexpected exception in controller '{self.name}': {e}")

    def _setup_wrappers(self):
        # note this could cause issues if a initialize fails because hardware is alrady initialized; in that
        # case _initialized will be marked as false even though hardware is ok. We could guard this but it's better to keep this stateless.
        original_init = self.initialize_hw
        original_deinit = self.deinitialize_hw

        def init_wrapper() -> bool:
            if result := original_init():
                self._initialized = True
            return result

        def deinit_wrapper() -> bool:
            if result := original_deinit():
                self._initialized = False
            return result

        self.initialize_hw = init_wrapper
        self.deinitialize_hw = deinit_wrapper
    
    def _set_initialized(self, value: bool):
        """
        Change the status of the controller to initialized/uninitialized.
        **NOTE**: this does not perform any hardware transaction (unlike `deinitialize_hw`). This method just updates a flag to notify the
        Hardware Manager System. 

        **Do not** call this if hardware crashes / becomes unresponsive in the `read/control` methods, instead raise a `HardwareCrash` exception. 
        """
        self._initialized = value
    
    # user overridable api

    def read(self):
        """
        This is called immediately before `control`. Override this to poll the hardware for incoming messages and react accordingly (e.g. check
        hardware status and log it). Overriding this method is optional.
        """
        pass
    
    @abstractmethod
    def control(self, commands: list[MotionCommand]):
        """
        Implement your custom control logic for a set of motion commands.
        
        Any exceptions raised by this method are interpreted as an hardware crash, and reset the controller state to uninitialized.
        The Hardware Manager System will automatically attempt to re-initialize.
        To trigger a hardware crash / reset, raise the `HardwareCrash` exception for clarity.
        """
    
    @abstractmethod
    def initialize_hw(self) -> bool:
        """Puts the hardware in a ready-to-operate state. Returns True on success or if already initialized."""

    @abstractmethod
    def deinitialize_hw(self) -> bool:
        """Puts the hardware at rest. Hardware should be re-initializable after this.
        Returns True on success or if already deinitialized."""
    
    def is_initialized(self) -> bool:
        """Wheter the hardware is succesfully initialized (if initialize_hw has been called succesfully).
        By default, this is handled automatically but could be overwritten with custom logic."""
        return self._initialized