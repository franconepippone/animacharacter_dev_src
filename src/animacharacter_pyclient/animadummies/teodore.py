from __future__ import annotations
from typing import Literal
from enum import Enum
from pathlib import Path

from base_components import Actuator, ActuatorGroup
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
    "CONTROL_TYPE"
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

    def __init__(self):
        self.eyes_h = Actuator(IDTABLE["EYES_H"])
        self.eyes_v = Actuator(IDTABLE["EYES_V"])
        self.eyes_focus = Actuator(IDTABLE["EYES_FOCUS"])
        self.eyelid_tr = Actuator(IDTABLE["EYELID_TR"])
        self.eyelid_tl = Actuator(IDTABLE["EYELID_TL"])
        self.eyelid_br = Actuator(IDTABLE["EYELID_BR"])
        self.eyelid_bl = Actuator(IDTABLE["EYELID_BL"])
        super().__init__(
            [self.eyes_h, self.eyes_v, self.eyes_focus, self.eyelid_bl, self.eyelid_br, self.eyelid_tl, self.eyelid_tr]
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

    def __init__(self):
        self.servo_r = Actuator(IDTABLE["SERVO_NECK_R"])
        self.servo_l = Actuator(IDTABLE["SERVO_NECK_L"])
        self.rotation = Actuator(IDTABLE["NECK_ROTATION"])
        super().__init__([self.servo_r, self.servo_l, self.rotation])
    
    # utility methods

    def tilt_head(self, forward: float, lateral: float):
        # TODO convert coordinates to servo motion
        pass

class HeadActuatorGroup(ActuatorGroup):
    """ Stores actuators for interacting
    with the head and neck animatronics"""

    def __init__(self):
        self.ear_left = Actuator(IDTABLE["EAR_LEFT"])
        self.ear_right = Actuator(IDTABLE["EAR_RIGHT"])
        self.mouth = Actuator(IDTABLE["MOUTH"])
        self.eyebox = EyeboxActuatorGroup()
        self.neck = NeckActuatorGroup()
        super().__init__([
            self.ear_left, self.ear_right, self.mouth,
            self.eyebox, self.neck
        ])

class ShoulderActuatorGroup(ActuatorGroup):
    """
    Stores actuators and utility methods for interacting
    with the animatronic's arm shoulder joint
    """

    def __init__(self, side: Literal["left", "right"]):
        self.motorA = Actuator(IDTABLE["ARMR_STEPPERA"] if side == "right" else IDTABLE["ARML_STEPPERA"])   
        self.motorB = Actuator(IDTABLE["ARMR_STEPPERB"] if side == "right" else IDTABLE["ARML_STEPPERB"])
        super().__init__([self.motorA, self.motorB])
    
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

    def __init__(self, side: Literal["left", "right"]):
        self.shoulder = ShoulderActuatorGroup(side)
        self.elbow = Actuator(IDTABLE["ARMR_ELBOW"] if side == "right" else IDTABLE["ARML_ELBOW"])
        self.wrist = Actuator(IDTABLE["ARMR_WRIST"] if side == "right" else IDTABLE["ARML_WRIST"])
        self.rotation = Actuator(IDTABLE["ARMR_ROTATION"] if side == "right" else IDTABLE["ARML_ROTATION"])
        super().__init__([self.elbow, self.wrist, self.rotation, self.shoulder])

    # TODO inverse kinematics
    def set_endpoint(self, x, y, z):
        pass 

class BodyActuatorGroup(ActuatorGroup):
    def __init__(self):
        self.lean = Actuator(IDTABLE["BODY_LEAN"])
        self.turn = Actuator(IDTABLE["BODY_ROTATION"])
        super().__init__([self.lean, self.turn])

class TeodoreDummy(ActuatorGroup):
    def __init__(self):
        self.head = HeadActuatorGroup()
        self.arm_left = ArmActuatorGroup("left")
        self.arm_right = ArmActuatorGroup("right")
        self.body = BodyActuatorGroup()
        super().__init__([self.head, self.arm_left, self.arm_right, self.body])


def create_dummy() -> TeodoreDummy:
    """
    Costructs and returns a teodore animadummy instance, the default animadummy for animacharacter platforms.
    
    :return: Description
    :rtype: ActuatorGroup
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
    print(x)

    packet = mech._gen_motiondata()

    print(packet)
    print()
    print(mech.arm_left.elbow._gen_motiondata())
    print()
    print(mech.head.eyebox._gen_motiondata())