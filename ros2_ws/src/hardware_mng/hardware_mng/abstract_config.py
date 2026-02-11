from typing import TypeVar, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .dispatcher import Dispatcher
from mcudrivers import BaseHardwareDriver # MAKE THIS A PROTOCOL INSTEAD? decouples from mcudrivers

T = TypeVar('T', bound=BaseHardwareDriver)

@dataclass
class DriverHolder:
    driver: BaseHardwareDriver
    loop_freq: float
    name: str

class AbstractConfiguration(ABC):
    """This class represent an abstract configuration for the hardware manager system.
    
    A configuration is a collection of data an functionalities that the hardware manager can use.
    - **Drivers**: each unique system using this hardware manager implementation can have different drivers.
        A driver is just a python class that provides an interface for interacting with any kind of hardware.
        This systems only support driver classes inherited from the mcudrivers.BaseHardwareDriver ABC.
    - **Dispatcher**: a dispatcher is the core component of the system. The hardware manager receives commands in the form
        (id, payload), where id represents the target hardware axys to actuate, and payload the command argument (position, speed).
        The dispatcher is what bridges between a (id, payload) abstract command to its actual implementation; to achieve this, it uses
        drivers as an abstraction layer.
    - **wakeup_drivers/shutdown_drivers**: methods that help manage the lifecycle of the drivers. They should be respectively responsible for
        initiating all communication with hardware, and deinitializing and closing communication with hardware, returning either True or False
        upon success on ALL registered drivers. Generally, they are automatically generated and should not be overwritten.

    When subclassing this class, in the init method use the scheme:   
    `self.driver_A = self.add_driver('my_custom_dA', DriverClass(...), loop_freq=50)`   
    The specified loop_freq will be the one at which the .drive_hardware() method on your driver will be called.
    
    Inside the configure_dispatcher method, use this scheme:  
    `dispatcher.register_handler(<positive integer id>, <handler callable>)`  
    A concrete example of this could be:  
    `dispatcher.register_handler(5, lambda payload: self.driver_A.write_axys_5(payload)))`
    If handlers require more complexity, create custom functions to use as handlers, or implement them in the 
    driver itself.

    """
    def __init__(self) -> None:
        self._drivers: Dict[str, DriverHolder] = {}

    def get_drivers(self):
        return self._drivers.values()

    def add_driver(self, name: str, driver_obj: T, loop_freq: float) -> T:
        self._drivers[name] = DriverHolder(driver_obj, loop_freq, name)
        return driver_obj

    @abstractmethod
    def configure_dispatcher(self, dispatcher: Dispatcher): ...

    def wakeup_drivers(self) -> bool:
        ok = True
        for dh in self.get_drivers():
            ok = ok and dh.driver.begin()
        return ok
    
    def shutdown_drivers(self) -> bool:
        ok = True
        for dh in self.get_drivers():
            ok = ok and dh.driver.deinit()
        return ok