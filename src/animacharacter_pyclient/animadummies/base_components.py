from __future__ import annotations
from typing import Any, Tuple, Iterable, List, Literal, Dict
from abc import ABC

from .. import json_tree as jt

# TODO make actuators with different values types (int8-16-32, uint8-16-32)?

class Actuator:
    """
    Represents a controllable axis on an animacharacter's platform. Value can be accessed and set through the `.value` property.\n
    or use `posefrom(<actuator>)` to copy the values from another actuator to this one, updating the value locally on this object.
    """

    def __init__(self, id: int, name: str = '', cfg_publisher: jt.Node | None = None):
        if not isinstance(id, int):
            raise TypeError("Actuator ID must be an integer")
        # In the future add more rigorous checks on ID validity (for example if in byte range 0-255)
        if id < 0:
            raise ValueError("Actuator ID must be a non-negative integer")
        self._value: float = 0
        self.cfgpub: jt.Node = cfg_publisher if cfg_publisher else jt.Node(name)
        self.id: int = id
        self.name: str = name

    @property
    def value(self) -> float:
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
    
    def configure(self, json_cfg: Dict):
        """
        Publish an arbitrary configuration json dictionary for this actuator. On server side,
        hardware controllers needs to be programmed to forward these configuration changes
        to the hardware.

        Use this method inside other more explicitly named methods, to make configuration easier.
        All calls to this method are merged until status is actually sent (via RemoteAnimacharacter.update()).
        """
        if self.cfgpub is None:
            raise RuntimeError(f"Actuator {self.id} is not bound to a jt.Node")
        key = f"{self.name}@{self.id}" # we encode the id in the json key
        self.cfgpub.publish(key, json_cfg)

    def _gen_motiondata(self) -> Tuple[int, int | float]:
        """Returns a simple representation of the actuator data: `tuple(<act_id>, <act_value>)`"""
        # TODO basic implementation, might need upgrading
        return (self.id, self._value)

    def __repr__(self) -> str:
        return f"Actuator(id={self.id}, value={self._value})"


class ActuatorGroup(ABC):
    """
    Base class for all kinds of actuator groups, can be thought as a 'dummy' of a part of a robotic system.
    Use `posefrom(<group>)` to copy the actuator values from `<group>` to this group (only changes the local state of the dummy).
    The copy operation is based on actuator IDs, so only actuators contained in this group or its subgroups with matching IDs will be updated.

    NOTE: actuators groups are immutable, so once initialized, their contents cannot (and should not) be changed.
    It's recommended to subclass this to create custom groups with fixed contents and members for easier and typed access to actuators and subgroups.
    """

    def __init__(self, contents: Iterable[Actuator | ActuatorGroup], cfg_publisher: jt.Node) -> None:
        self._actuatorsarray: Tuple[Actuator, ...] = tuple([c for c in contents if isinstance(c, Actuator)])
        self._subgroupsarray: Tuple[ActuatorGroup, ...]  = tuple([c for c in contents if isinstance(c, ActuatorGroup)])
        self._act_table: Dict[int, Actuator] = {act.id : act for act in self._actuatorsarray}
        self._fill_missing_act_names()

        self.cfgpub: jt.Node = cfg_publisher

        # TODO further optimize this by creating _all_actuators field that contains all actuators contained in this whole branch. Easier
        # to do _gen_motionpacket then or to check for ownership


        # TODO this allows using posefrom to modify actuators in subgroups of this group. Keep it? The subgroups are immutable anyway, 
        # and should already be initialized
        for sg in self._subgroupsarray:
            self._act_table.update(sg._act_table)
    
    def _fill_missing_act_names(self):
        # called upon __init__, names all unnamed actuators with attribute name
        for attr, value in vars(self).items():
            if isinstance(value, Actuator) and value.name == '':
                value.name = attr


    def _compute_act_names(self) -> dict[int, str]:
        act_names = {}

        # first pass: use explicit actuator names
        for act in self._act_table.values():
            act_names[act.id] = act.name

        # second pass: infer names from attributes if missing
        for attr, value in vars(self).items():
            if isinstance(value, Actuator) and value.id not in act_names:
                act_names[value.id] = attr

        return act_names


    def posefrom(self, group: ActuatorGroup):
        """
        Copy actuators values from the given group to this group (includes subgroups), based on actuator IDs.
        """
 
        for act in group._actuatorsarray:
            if act.id in self._act_table:
                self._act_table[act.id].posefrom(act)

    def get_actuators(self) -> Tuple[Actuator, ...]:
        """Returns a container with all the actuators in this group."""
        return self._actuatorsarray
    
    def get_subgroups(self) -> Tuple[ActuatorGroup, ...]:
        """Returns a container with all the subgroups contained in this group."""
        return self._subgroupsarray

    def _gen_motiondata(self) -> List[Tuple[int, float]]:
        # generates the whole packet data (recursively) -> ([id, value], [id, value], ...)
        datalist = [act._gen_motiondata() for act in self._actuatorsarray]
        for sg in self._subgroupsarray:
            datalist += sg._gen_motiondata()
        
        return datalist
    
    def __repr__(self):
        return self._repr()

    def _repr(self, prefix="", is_last=True):
        name = f"Group {self.__class__.__name__}"

        # generate id - name table for actuators
        act_names = {}
        for act in self._act_table.values():
            act_names[act.id] = act.name

        if prefix:
            connector = "└── " if is_last else "├── "
            line = prefix + connector + name
        else:
            line = name  # root

        lines = [line]

        children = self._actuatorsarray + self._subgroupsarray
        next_prefix = prefix + ("    " if is_last else "│   ")

        for i, child in enumerate(children):
            last = i == len(children) - 1

            if isinstance(child, ActuatorGroup):
                lines.append(child._repr(next_prefix, last))
            else:
                connector = "└── " if last else "├── "
                lines.append(
                    f"{next_prefix}{connector} {act_names[child.id]} ─ id: {child.id}"
                )

        return "\n".join(lines)