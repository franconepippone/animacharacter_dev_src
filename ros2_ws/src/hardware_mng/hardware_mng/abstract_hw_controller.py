from collections.abc import Iterable, Callable
from typing import NamedTuple, Optional, Tuple, Dict, Any, TypeVar, Type

from rclpy.logging import RcutilsLogger
from abc import ABC, abstractmethod
from queue import Queue, Empty
from .looper import LoopActionRequest, LoopAction
from .databus import Databus, DataReader, DataWriter

SPECIAL_PATH_CHARS = {'@'}

# ensures format of config path is correct
def _cleanup_path(path: str) -> Tuple[str, ...]:
    invalid = set(path) & SPECIAL_PATH_CHARS
    if invalid:
        raise ValueError(f"Path contains invalid characters: {invalid}")
    parts = path.split('/')
    parts = (part for part in parts if part.strip() != '')
    return tuple(parts)

# attempts to get an object within a nested dict tree

def _fetch_dict_deep(d: Dict[str, Any], keys: Tuple[str, ...]) -> Tuple[bool, Any]:
    """
    Iteratively fetch a value from a nested dictionary using a list of keys.
    Returns a tuple of (succ, value): succ is True if key was found.
    """
    current: Any = d

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]

    return True, current

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


T = TypeVar('T')


class BaseHardwareController(ABC):
    """
    A Hardware Controller or Module is responsible for the execution of motion commands. Hardware controller
    are highly coupled to hardware and might differ from robot to robot. A single robot might use multiple hardware controllers.
    A Hardware Controller "subscribes" to a set of motion command ids (command_group set, passed in __init__ or via `subscribe_to_command_group`). All the recevied commands witch matching ids will be
    passed to the `control` method of the subscribed hardware controllers at a frequency specified by flush_frequency. The control method handles updating the
    hardware with the received motion commands values. 

    Based on hardware implementation, the `control` method could either directly update hardware command per command, or could batch all updates in one hardware
    update communication (ideal solution). In any case, implementation of `control` is completely up to the user, but must always take less than a loop period to ensure 
    a constant update frequency. A `read` method can be overwritten to perfrom read-only operations on the hardware. This is called just before "control", and is just for
    clarity (everything done in `read` can also be done at the start of `control`).

    Low-frequency hardware configuration changes (i.e. motor_max_speed, limits, operating mode...) are exchanged as a pure user-defined json dictionary.
    A controller can subscribe to a specific config path (a path within the config json tree) with a handler using `subscribe_to_config_path(path, handlr)`; the handler will be invoked when the path
    exists within the received configuration json tree, and the corresponding value (potentially more json) will be passed to it.

    Note that `control`, `read` and all the config handlers are always called from the same thread, meaning that they are naturally thread safe (they can interact with shared
    state).

    Hardware controllers are dynamically loaded as a plugins by the hardware manager system. A Hardware Configuration is a set of hardware controllers that are loaded and used
    by the hardware manager system. A Configuration can be registered in the `hw_configurations.yaml` file, and then used by passing it as an argument when launching
    the hardware manager system or by optionally setting it as default by defining `default_config: <your-cfg-name>` in the yaml file.
    """
    _databus: Databus | None = None # to be set externally later
    
    def __init__(self, name: str, flush_freq: float, command_group: set[int] = set()) -> None:
        self.name = name
        self.flush_freq = flush_freq # flush frequency in Hz
        self.command_group = command_group
        self._config_handlers: dict[Tuple[str, ...], Callable] = {}
        self._cfg_updates_queue: Queue[dict] = Queue()
        self._initialized = False

        if self.flush_freq <= 0:
            raise ValueError(f"flush_freq must be positive, got {self.flush_freq}")

        self.logger = RcutilsLogger(f"HWController-{self.name}")
        self._setup_wrappers()

    # shared databus api

    def create_databus_writer(self, topic: str, data_type: type[T], initial: T) -> DataWriter[T]:
        """Create a writer on the shared databus across all controllers. Any controller can read the data
        posted by a writer. Writers enforce a unique writable data type, which must be immutable. 
        An initial value is required to initialize the bus with.
        
        This can only be done at controller initialization. Writers cannot be created at runtime.
        """
        if not isinstance(self._databus, Databus):
            raise ValueError('Hardware controller has no bound databus (something went wrong on initialization?)')
        
        return self._databus.create_writer(topic, data_type, initial)

    
    def create_databus_reader(self, topic: str, data_type: Type[T]) -> DataReader[T]:
        """Create a reader of the shared databus across all controllers. Use a reader to read
        data posted by other controllers. Data type must match that specified by the topic writer
        
        This can only be done at controller initialization. Readers cannot be created at runtime.
        """
        if not isinstance(self._databus, Databus):
            raise ValueError('Hardware controller has no bound databus (something went wrong on initialization?)')
        
        return self._databus.create_reader(topic, data_type)
    
    # subscription to motion commands

    def subscribe_to_command_group(self, ids_group: Iterable[int]):
        """If not passed to __init__, use this to subscribe to a set of motion commands"""
        self.command_group = set(ids_group)
    
    # handling configuration

    def subscribe_to_config_path(self, path: str, handler: Callable[[dict], Any]):
        """Bind a handler function to a specified path within the configuration tree.
        Upon reception of a configuration tree in which this path exists, this handler will be invoked with the corresponding
        configuration data contained under that path.
        """
        parts = _cleanup_path(path)
        if hasattr(self._config_handlers, path):
            self.logger.warn(f"Overriding config handler for '{path}'")
        self._config_handlers[parts] = handler

    def _queue_config_update(self, config: dict):
        """
        Queues a config dictionary in a thread safe way, so that handlers can be executed
        deferredly on next loop iteration.
        """
        self._cfg_updates_queue.put(config)

    def _execute_queued_config_updates(self):
        # dispatches configs until queue is empty
        while self._cfg_updates_queue.qsize() > 0:
            configs = self._cfg_updates_queue.get()
            self._dispatch_config(configs)
            

    def _dispatch_config(self, global_config: dict):
        """Dispatches the appropriate branch of the config tree to registered handlers.
        
        NOTE: This should be called from the same thread of control() and read(). Call
        _queue_config_update instead if you are in a different thread.
        """
        for path_parts, handler in self._config_handlers.items():
            succ, subconfig = _fetch_dict_deep(global_config, path_parts)
            if succ:
                try:
                    handler(subconfig)
                except Exception as e:
                    self.logger.error(f"Configuration handler '{handler.__name__}' subscribed to '{'/'.join(path_parts)}' failed -> {e}")
                    #raise HardwareCrash from e

    # this is used as the "job" of the looper
    def _flush(self, incoming_commands: Queue[MotionCommand], _outgoing_commands: Queue[MotionCommand]) -> Optional[LoopActionRequest]:
            if not self.is_initialized(): self.logger.warning(f"'_flush' was called but controller is marked as initialized (this should never happen)")
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
                self._execute_queued_config_updates()
                self.read() # first check for any data
                self.control(commands) # then write command instructions
            
            except HardwareCrash as e:
                self.logger.error(f"Hardware crash in controller '{self.name}': {e}")
                self._set_initialized(False)
                return LoopActionRequest(LoopAction.STOP)
            
            except Exception as e:
                # we interpret an exception as an hardware failure and reset the state to uninitialized
                self.logger.error(f"Unexpected exception in controller '{self.name}': {e}")
                self._set_initialized(False)
                return LoopActionRequest(LoopAction.STOP)

    def _setup_wrappers(self):
        # explicitly applying "decorators" to init/denit methods to keep track of init status.
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