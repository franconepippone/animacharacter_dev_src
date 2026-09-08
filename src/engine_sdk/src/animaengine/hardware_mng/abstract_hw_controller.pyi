import abc
from .databus import DataReader as DataReader, DataWriter as DataWriter, Databus as Databus
from _typeshed import Incomplete
from abc import ABC, abstractmethod
from collections.abc import Callable as Callable, Iterable
from typing import Any, NamedTuple, Type, TypeVar
class ControllerException(Exception):
    """Base class for all exceptions a controller can volountarily raise."""
    code: Incomplete
    description: Incomplete
    def __init__(self, code: int, description: str, *args: object) -> None: ...
class ControllerWarning(ControllerException):
    """
    Publish a warning with given code and description, alerting the system of something. If a status panel is
    present, this warning will also be redirected there.

    Raising this does not stop nor reset the controller, just alerts the system. 
    """
class ControllerError(ControllerException):
    """
    Trigger a controller reset. The controller will be put in a deinitialized state, allowing the 
    Hardware Manager to try to re-initialize it automatically.
    
    Raise this in `read` or `control` if the hardware becomes unresponsive and you want to trigger a reset.
    """
class ControllerFatal(ControllerException):
    """
    Triggers a global system shutdown. All controllers, running processes, current session with client will attempt to be gracefully 
    interrupted and deinitialied. System will enter a CRASHED state, and will require a manual reboot.

    Raise this if something catastrophical is happening (there's a fire? Robot is destroying itself? Person to close detected?)
    """
class MotionCommand(NamedTuple):
    id: int
    value: float
T = TypeVar('T')
class BaseHardwareController(ABC, metaclass=abc.ABCMeta):
    '''
    A Hardware Controller or *Hardware Module* is responsible for the execution of motion commands. Hardware controller
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

    Controllers can communicate between each other thanks to a shared :class:`Databus`. Use `create_databus_writer` and
    `create_databus_reader` methods to create databus reader/writer objects.
    Using the databus allows to implement closed control loops that span over multiple controllers (i.e. robot head stabilization based on
    robot torso orientation). In addition, distrubuted architectures where there are dedicated "*driver* controllers" (interface hardware) and "*logical* controllers"
    (run control algorithms) can be used for more composable and flexible systems. 

    Controller may intentionally raise three kinds of exceptions, derived from the `ControllerException` class:
    - :class:`ControllerWarning` : globally alert the system of something controller-related;
    - :class:`ControllerError` : alert system and causes a controller reset;
    - :class:`ControllerFatal` : trigger a global system shutdown (all processes of the engine are interrupted).

    Hardware controllers are dynamically loaded as a plugins by the hardware manager system. A Hardware Configuration is a set of hardware controllers that are loaded and used
    by the hardware manager system. A Configuration can be registered in the `hw_configurations.yaml` file, and then used by passing it as an argument when launching
    the hardware manager system or by optionally setting it as default by defining `default_config: <your-cfg-name>` in the yaml file.
    '''
    name: Incomplete
    flush_freq: Incomplete
    command_group: Incomplete
    logger: Incomplete
    def __init__(self, name: str, flush_freq: float, command_group: set[int] = ...) -> None: ...
    def create_databus_writer(self, topic: str, data_type: type[T], initial: T) -> DataWriter[T]:
        """Create a writer on the shared databus across all controllers. Any controller can read the data
        posted by a writer. Writers enforce a unique writable data type, which must be immutable. 
        An initial value is required to initialize the bus with.
        
        This can only be done at controller instantiation. Writers cannot be created at runtime.
        """
    def create_databus_reader(self, topic: str, data_type: Type[T]) -> DataReader[T]:
        """Create a reader of the shared databus across all controllers. Use a reader to read
        data posted by other controllers. Data type must match that specified by the topic writer
        
        This can only be done at controller instantiation. Readers cannot be created at runtime.
        """
    def subscribe_to_command_group(self, ids_group: Iterable[int]):
        """If not passed to __init__, use this to subscribe to a set of motion commands"""
    def subscribe_to_config_path(self, path: str, handler: Callable[[Any], Any], enforce_type: bool = False):
        """Bind a handler function to a specified path within the configuration tree.
        Upon reception of a configuration tree in which this path exists, this handler will be invoked with the corresponding
        configuration data contained under that path.

        If `enforce_type=True`, the type annotation used in the handler will be runtime-checked; data with wrong format will
        be rejected. Since data is in json format, usage of a :class:`typing_extensions.TypedDict` annotation is ideal. Runtime type checking is 
        done with *pydantic* Adapters.
        """
    def read(self) -> None:
        """
        This is called immediately before `control`. Override this to poll the hardware for incoming messages and react accordingly (e.g. check
        hardware status and log it). Overriding this method is optional.
        """
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
