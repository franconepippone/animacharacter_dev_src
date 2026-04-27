from __future__ import annotations
from typing import Literal
from enum import Enum
from pathlib import Path

from .base_components import Actuator, ActuatorGroup

from ..config_tree.utils import ConfigNode
import tomllib

# hack to load the file next to this one
with open(Path(__file__).parent / "teodore.toml", "rb") as f:
    data = tomllib.load(f)

IDTABLE = {act["name"]: act["id"] for act in data["channels"]}
print(IDTABLE)

# NOTE that the classes should never be created directly, but through the create_dummy() factory function
__all__ = [
    "EyeboxActuatorGroup",
    "NeckActuatorGroup",
    "HeadActuatorGroup",
    "ShoulderActuatorGroup",
    "ArmActuatorGroup",
    "ArmActuatorGroup",
    "TeodoreDummy",
    "CONTROL_TYPE",
    "create_dummy"
]


class CONTROL_TYPE(Enum):
    DIRECT = 1
    TRAPEZOIDAL_VELOCITY = 2
    SMOOTH_EXPONENTIAL = 3
    
class EyeboxActuatorGroup(ActuatorGroup):
    """ 
    Stores actuators and utility methods for interacting
    with the eyebox mechanism.
    """

    def __init__(self, parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('eyes', parent_cfg)
        self.eyes_h = Actuator(IDTABLE["EYES_H"], config_publisher=my_cfg)
        self.eyes_v = Actuator(IDTABLE["EYES_V"], config_publisher=my_cfg)
        self.eyes_focus = Actuator(IDTABLE["EYES_FOCUS"], config_publisher=my_cfg)
        self.eyelid_tr = Actuator(IDTABLE["EYELID_TR"], config_publisher=my_cfg)
        self.eyelid_tl = Actuator(IDTABLE["EYELID_TL"], config_publisher=my_cfg)
        self.eyelid_br = Actuator(IDTABLE["EYELID_BR"], config_publisher=my_cfg)
        self.eyelid_bl = Actuator(IDTABLE["EYELID_BL"], config_publisher=my_cfg)
        super().__init__(
            [self.eyes_h, self.eyes_v, self.eyes_focus, self.eyelid_bl, self.eyelid_br, self.eyelid_tl, self.eyelid_tr],
            my_cfg
        )

    # Utility methods
    def look_at(self) -> None:
        pass
    
    def eyelids_set_open(self) -> None:
        pass

    def eyelids_set_center(self) -> None:
        pass

class NeckActuatorGroup(ActuatorGroup):
    """ 
    Stores actuators and utility methods for rotating the head in
    three different axys
    """

    def __init__(self, parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('neck', parent_cfg)
        self.servo_r = Actuator(IDTABLE["SERVO_NECK_R"], config_publisher=my_cfg)
        self.servo_l = Actuator(IDTABLE["SERVO_NECK_L"], config_publisher=my_cfg)
        self.rotation = Actuator(IDTABLE["NECK_ROTATION"], config_publisher=my_cfg)
        super().__init__([self.servo_r, self.servo_l, self.rotation], my_cfg)
    
    # utility methods

    def tilt_head(self, forward: float, lateral: float):
        # TODO convert coordinates to servo motion
        pass

class TorsoActuatorGroup(ActuatorGroup):
    def __init__(self, parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('torso', parent_cfg)
        self.neck = NeckActuatorGroup(my_cfg)
        super().__init__([self.neck
        ], my_cfg)

class HeadActuatorGroup(ActuatorGroup):
    """ Stores actuators for interacting
    with the head and neck animatronics"""

    def __init__(self, parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('head', parent_cfg)
        self.ear_left = Actuator(IDTABLE["EAR_LEFT"], config_publisher=my_cfg)
        self.ear_right = Actuator(IDTABLE["EAR_RIGHT"], config_publisher=my_cfg)
        self.mouth = Actuator(IDTABLE["MOUTH"], config_publisher=my_cfg)
        self.eyebox = EyeboxActuatorGroup(my_cfg)
        self.neck = NeckActuatorGroup(my_cfg)
        super().__init__([
            self.ear_left, self.ear_right, self.mouth,
            self.eyebox, self.neck
        ], my_cfg)

class ShoulderActuatorGroup(ActuatorGroup):
    """
    Stores actuators and utility methods for interacting
    with the animatronic's arm shoulder joint
    """

    def __init__(self, side: Literal["left", "right"], parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('shoulder', parent_cfg)
        self.motorA = Actuator(IDTABLE["ARMR_STEPPERA"] if side == "right" else IDTABLE["ARML_STEPPERA"], config_publisher=my_cfg)   
        self.motorB = Actuator(IDTABLE["ARMR_STEPPERB"] if side == "right" else IDTABLE["ARML_STEPPERB"], config_publisher=my_cfg)
        super().__init__([self.motorA, self.motorB], my_cfg)
    
    # utility methods
    def abduct(self, value: int):
        pass

    def extend(self, value):
        pass

class ArmActuatorGroup(ActuatorGroup):
    """
    Stores actuators and utility methods for interacting
    with an animatronic arm
    """

    def __init__(self, side: Literal["left", "right"], parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode(f'arm_{side}', parent_cfg)
        self.shoulder = ShoulderActuatorGroup(side, my_cfg)
        self.elbow = Actuator(IDTABLE["ARMR_ELBOW"] if side == "right" else IDTABLE["ARML_ELBOW"], config_publisher=my_cfg)
        self.wrist = Actuator(IDTABLE["ARMR_WRIST"] if side == "right" else IDTABLE["ARML_WRIST"], config_publisher=my_cfg)
        self.rotation = Actuator(IDTABLE["ARMR_ROTATION"] if side == "right" else IDTABLE["ARML_ROTATION"], config_publisher=my_cfg)
        super().__init__([self.elbow, self.wrist, self.rotation, self.shoulder], my_cfg)

    # TODO inverse kinematics
    def set_endpoint(self, x, y, z):
        pass 

class BodyActuatorGroup(ActuatorGroup):
    def __init__(self, parent_cfg: ConfigNode | None = None):
        my_cfg = ConfigNode('body', parent_cfg)
        self.lean = Actuator(IDTABLE["BODY_LEAN"], config_publisher=my_cfg)
        self.turn = Actuator(IDTABLE["BODY_ROTATION"], config_publisher=my_cfg)
        super().__init__([self.lean, self.turn], my_cfg)

class TeodoreDummy(ActuatorGroup):
    def __init__(self):
        root_cfg = ConfigNode('')
        self.head = HeadActuatorGroup(root_cfg)
        self.arm_left = ArmActuatorGroup("left", root_cfg)
        self.arm_right = ArmActuatorGroup("right", root_cfg)
        self.body = BodyActuatorGroup(root_cfg)
        super().__init__([self.head, self.arm_left, self.arm_right, self.body], root_cfg)



def create_dummy() -> TeodoreDummy:
    """
    Costructs and returns a teodore animadummy instance, the default animadummy for animacharacter platforms.
    """
    return TeodoreDummy()

if __name__ == "__main__":

    mech = create_dummy()
    dummy2 = create_dummy()

    dummy2.arm_left.shoulder.motorA.value = 10
    dummy2.head.eyebox.eyes_h.value = 1.5

    mech.arm_left.elbow.value = 3.2
    mech.head.mouth.value = 0.4
    dummy2.posefrom(mech)

    x = mech.head.get_subgroups()
    x = HeadActuatorGroup()
    print(mech)

    packet = mech._gen_motiondata()

    #print(packet)
    #print()
    #print(mech.arm_left.elbow._gen_motiondata())
    #print()
    #print(mech.head.eyebox._gen_motiondata())