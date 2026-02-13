"""
The class represents an abstract configuration for the hardware manager system.
A configuration is a collection of data and functionality that the hardware
manager uses to operate a specific hardware setup.

- Drivers:
  Each system using this hardware manager implementation may define its own
  set of drivers. A driver is a Python class that provides an interface for
  interacting with hardware. Drivers must implement the expected driver
  interface (e.g., begin(), deinit(), flush() methods).

  The flush() is the method responsible for updating the hardware with the currently
  stored joint/actuator state. This method will be called at a fixed frequency 
  automatically when the system is active, in a separate threads (keep thread safety in mind).
  
  Usually a driver exposes write() methods that modify the internal state/representation of joints.
  The flush() is there to send this state to the hardware.

- Dispatcher:
  The dispatcher is the core routing component of the system. The hardware
  manager receives abstract commands in the form (id, payload), where `id`
  identifies the target hardware axis to actuate and `payload` represents
  the command argument (e.g., position, speed).

  The dispatcher bridges the abstract (id, payload) command to its concrete
  implementation by mapping each id to a handler that typically calls into
  a driver.

  NOTE about BatchDispatcher:
  The BatchDispatcher is a wrapper around a Dispatcher that allows optional
  batching of dispatches based on sets of ids. This is typically used to group
  commands by driver ownership, so that setup (e.g., lock acquisition) and
  cleanup (e.g., lock release) logic can be executed once per driver rather
  than once per command.

  If drivers require setup/cleanup logic before transmission, define a batch
  for each subset of ids associated with that driver and configure the
  corresponding context logic accordingly (see `dispatcher.hooks_to_context`
  for creating a context manager from simple pre/post functions).
  Usually the context is just a lock, that needs to be acquired to avoid racing with
  the thread constantly calling flush() (flush internally acquires the same lock).

- wakeup_drivers / shutdown_drivers:
  These methods manage the driver lifecycle. They are responsible for
  initializing all communication with the hardware and properly shutting
  it down. Each returns True only if all registered drivers succeed.
  They are already provided automatically and, if the drivers implement the begin/deinit
  methods properly, there should be no need to overwrite them.

When subclassing this class:

- In __init__, register drivers using:
      self.driver_A = self.add_driver("my_custom_dA", DriverClass(...), loop_freq=50)

  The specified loop_freq determines the frequency at witch the driver's flush() method is executed.

- In configure_dispatcher, register handlers using:
      dispatcher.register_handler(<positive integer id>, <handler callable>)

  Example:
      dispatcher.register_handler(
          5,
          lambda payload: self.driver_A.write_axys_5(payload)
      )

    If more complex logic is required, define custom handler functions or
    implement the necessary behavior directly inside the driver.

- In configure_batch_dispatcher, add dispatch groups using:
    batch_dispatcher.add_batch(
            {<set of ids belonging to this group>},
            <context manager for setup/cleanup logic>
        )
    
    Example:
        batch_dispatcher.add_batch(
            {1, 2, 3, 4, 5},
            self.driver_A.get_batch_write_context_manager() # assuming ctxmng is provided by the driver itself
        )

"""

from typing import TypeVar, Dict, Any, Iterable, Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .dispatcher import Dispatcher, BatchDispatcher, hooks_to_context

# -------------------- Driver Protocol --------------------
class HardwareDriverProtocol(Protocol):
    """Protocol for any hardware driver compatible with the hardware manager."""

    def begin(self) -> bool:
        """Initialize and start communication with the hardware."""
        ...

    def deinit(self) -> bool:
        """Deinitialize and stop communication with the hardware."""
        ...

    def flush(self) -> Any:
        """Updateds the the hardware."""
        ...

# Generic type for drivers
T = TypeVar('T', bound=HardwareDriverProtocol)


# -------------------- Driver Wrapper --------------------
@dataclass
class DriverHolder:
    driver: HardwareDriverProtocol
    loop_freq: float
    name: str

    def __post_init__(self):
        if self.loop_freq <= 0:
            raise ValueError(f"loop_freq must be positive, got {self.loop_freq}")

# -------------------- Abstract Configuration --------------------
class AbstractHMSConfiguration(ABC):
    """
    This class represents an abstract configuration for the Hardware Manager System.  
    A configuration is a collection of data and functionality that the hardware
    manager uses to operate a specific hardware setup.

    - **Drivers**: A driver is just a Python class that provides an abstraction layer for
        interacting with hardware.
        Any class implementing the HardwareDriverProtocol is a valid driver; mainly this means
        exposing a 'flush' method, which takes zero arguments, that updates hardware based on a stored state. 
        The implementation is completely up to the user.

    - **Dispatcher**: a dispatcher is the core component of the system. 
        The hardware manager receives commands in the form (id, payload), 
        where id represents the target hardware axys to actuate, and payload the command argument (position, speed). 
        The dispatcher is what bridges between a (id, payload) abstract command to its 
        actual implementation; to achieve this, it uses drivers as an abstraction layer.

    - **BatchDispatcher**: The batch dispatcher is simply a wrapper around a dispatcher object that allows,
        if necessary, to batch dispatches based on sets of ids. 
        This in general should be used to group dispatches based on driver ownership of ids, so that setup 
        (such as lock acquisition) and cleanup (lock release) logic can be executed PER driver. 
        Put simply, if your drivers need setup/cleanup logic before a transmission just add a batch 
        for each subset of ids directed to that driver and configure pre/post hooks accordingly 
        (look into 'dispatcher.hooks_to_context' function to automatically create a ctx manager from functions).
    """

    def __init__(self) -> None:
        self._drivers: Dict[str, DriverHolder] = {}

    # -------------------- Driver Management --------------------
    def get_drivers(self) -> Iterable[DriverHolder]:
        """Return all registered drivers."""
        return self._drivers.values()

    def add_driver(self, name: str, driver_obj: T, loop_freq: float) -> T:
        """
        Register a driver with a name and loop frequency.

        Args:
            name (str): Unique driver identifier.
            driver_obj: Instance implementing HardwareDriverProtocol.
            loop_freq (float): Frequency in Hz at which the driver's drive_hardware method will be called.

        Returns:
            The driver object (for convenience).
        """
        if name in self._drivers:
            raise ValueError(f"Driver with name '{name}' already exists")
        self._drivers[name] = DriverHolder(driver_obj, loop_freq, name)
        return driver_obj

    # -------------------- Dispatcher Configuration --------------------
    @abstractmethod
    def configure_dispatcher(self, dispatcher: Dispatcher[int, float]):
        """Register handlers mapping ids to driver methods (one id per hardware axys)."""
        ...

    @abstractmethod
    def configure_batch_dispatcher(self, batch_dispatcher: BatchDispatcher[int, float]):
        """Add batches from a set of ids with optional context managers for grouped dispatches.
        Example usage:
        ```
        batch_dispatcher.add_batch(
            set(id1, id2, id3, id4, id5, ...), # all ids from the driver 1 group 
            self.driver1.batch_context_mng # example of a context manager for batch writing, provided from an example driver
        )
        batch_dispatcher.add_batch(
            set(id10, id11, id12, id13, id14, ...), 
            hooks_to_context(pre_func, post_func) # example of creating a ctx mng with pre/post functions
        )
        ```
        """
        ...

    # -------------------- Driver Lifecycle --------------------
    def wakeup_drivers(self) -> bool:
        """Initialize all drivers. Short-circuits on first failure."""
        for dh in self.get_drivers():
            if not dh.driver.begin():
                return False
        return True

    def shutdown_drivers(self) -> bool:
        """Deinitialize all drivers. Short-circuits on first failure."""
        for dh in self.get_drivers():
            if not dh.driver.deinit():
                return False
        return True
