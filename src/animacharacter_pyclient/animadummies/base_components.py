from __future__ import annotations
from typing import Any, Tuple, Iterable, List, Literal, Dict
from abc import ABC, abstractmethod
from enum import Enum


# TODO make actuators with different values types (int8-16-32, uint8-16-32)?

class Actuator:
    """
    Represents a controllable axys on an animacharacter's platform. Value can be accessed and set through the `.value` property.\n
    or use `posefrom(<actuator>)` to copy the values from another actuator to this one, updating the value locally on this object.
    """

    def __init__(self, ID: int):
        self._value = 0
        if not isinstance(ID, int):
            raise TypeError("Actuator ID must be an integer")
        # In the future add more rigorous checks on ID validity (for example if in byte range 0-255)
        if ID < 0:
            raise ValueError("Actuator ID must be a non-negative integer")
        self.ID = ID

    @property
    def value(self):
        return self._value
    
    def _validate_new_value(self, val: float) -> float:
        # TODO performs all restrictions and checks to val before assigning it 
        return val
    
    @value.setter
    def value(self, val: float):
        self._value = self._validate_new_value(val)

    def posefrom(self, actuator: Actuator):
        """Copy value from the given actuator to this actuator. Does NOT send
        update to the animacharacter (only updates local value)."""
        # implements copying the pose information from actuator to actuatr
        self._value = self._validate_new_value(actuator.value)
    
    # how to ahndle this?
    """
    def config(self, configs: Dict):
        ""Sends an arbitrary config dict (this method is ment to be used by other methods of subclasses
        that allow modifying actuator specific configurations more easily).""
        self._server_link.send_config(configs)
    """

    def _gen_motiondata(self) -> Tuple[int, int | float]:
        """Returns a simple representation of the actuator data: `tuple(<act_id>, <act_value>)`"""
        # TODO basic implementation, might need upgrading
        return (self.ID, self._value)

    def __repr__(self) -> str:
        return f"Actuator(id={self.ID}, value={self._value})"


class ActuatorGroup(ABC):
    """
    Base class for all kinds of actuator groups, can be thought as a 'dummy' of a part of a robotic system.
    Use `posefrom(<group>)` to copy the actuator values from `<group>` to this group (only changes the local state of the dummy).
    The copy operation is based on actuator IDs, so only actuators contained in this group or its subgroups with matching IDs will be updated.

    NOTE: actuators groups are ment to be immutable, so once initialized, their contents should not be changed.
    It's recommended to subclass this to create custom groups with fixed contents and members for easier and typed access to actuators and subgroups.
    """

    def __init__(self, contents: Iterable[Actuator | ActuatorGroup]) -> None:
        self._actuatorsarray: Tuple[Actuator, ...] = tuple([c for c in contents if isinstance(c, Actuator)])
        self._subgroupsarray: Tuple[ActuatorGroup, ...]  = tuple([c for c in contents if isinstance(c, ActuatorGroup)])
        self._act_table: Dict[int, Actuator] = {act.ID : act for act in self._actuatorsarray}

        # TODO this allows using posefrom to modify actuators in subgroups of this group. Keep it? The subgroups are immutable anyway, 
        # and should already be initialized
        for sg in self._subgroupsarray:
            self._act_table.update(sg._act_table)

    def posefrom(self, group: ActuatorGroup):
        """
        Copy actuators values from the given group to this group (includes subgroups), based on actuator IDs.
        """
 
        for act in group._actuatorsarray:
            if act.ID in self._act_table:
                self._act_table[act.ID].posefrom(act)

    def get_actuators(self) -> Tuple[Actuator, ...]:
        """Returns a container with all the actuators in this group."""
        return self._actuatorsarray
    
    def get_subgroups(self) -> Tuple[ActuatorGroup, ...]:
        """Returns a container with all the subgroups contained in this group."""
        return self._subgroupsarray

    def _gen_motiondata(self) -> List[Tuple[int, float | int]]:
        # generates the whole packet data (recursively) -> ([id, value], [id, value], ...)
        datalist = [act._gen_motiondata() for act in self._actuatorsarray]
        for sg in self._subgroupsarray:
            datalist += sg._gen_motiondata()
        
        return datalist
  
    def __repr__(self) -> str:
        return f"ActuatorGroup(#actuators={len(self._actuatorsarray)}, #subgroups={len(self._subgroupsarray)})"
