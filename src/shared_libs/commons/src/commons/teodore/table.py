from dataclasses import dataclass

@dataclass
class actuator:
    id: int
    group: str


HEAD_GROUP = 'head'
BODY_GROUP = 'body'
LEFT_ARM_GROUP = 'leftarm'
RIGHT_ARM_GROUP = 'rightarm'

class teodore_actuator_table:
    # HEAD
    EYES_H = actuator(1, HEAD_GROUP)
    EYES_V = actuator(2, HEAD_GROUP)
    EYES_FOCUS = actuator(3, HEAD_GROUP)
    EYELID_TR = actuator(4, HEAD_GROUP)
    EYELID_TL = actuator(5, HEAD_GROUP)
    EYELID_BR = actuator(6, HEAD_GROUP)
    EYELID_BL = actuator(7, HEAD_GROUP)
    EAR_LEFT = actuator(8, HEAD_GROUP)
    EAR_RIGHT = actuator(9, HEAD_GROUP)
    MOUTH = actuator(10, HEAD_GROUP)

    # NECK
    SERVO_NECK_R = actuator(11, HEAD_GROUP)
    SERVO_NECK_L = actuator(12, HEAD_GROUP)
    NECK_ROTATION = actuator(13, BODY_GROUP)

    # ARM RIGHT
    ARMR_STEPPERA = actuator(14, RIGHT_ARM_GROUP)
    ARMR_STEPPERB = actuator(15, RIGHT_ARM_GROUP)
    ARMR_ELBOW = actuator(16, RIGHT_ARM_GROUP)
    ARMR_WRIST = actuator(17, RIGHT_ARM_GROUP)
    ARMR_ROTATION = actuator(18, RIGHT_ARM_GROUP)

    # ARM LEFT
    ARML_STEPPERA = actuator(19, LEFT_ARM_GROUP)
    ARML_STEPPERB = actuator(20, LEFT_ARM_GROUP)
    ARML_ELBOW = actuator(21, LEFT_ARM_GROUP)
    ARML_WRIST = actuator(22, LEFT_ARM_GROUP)
    ARML_ROTATION = actuator(23, LEFT_ARM_GROUP)

    # BODY
    BODY_LEAN = actuator(24, BODY_GROUP)
    BODY_ROTATION = actuator(25, BODY_GROUP)
    BODY_TILT = actuator(26, BODY_GROUP)

    # LEDS
    LED_IRIS_LEFT = actuator(27, HEAD_GROUP)
    LED_IRIS_RIGHT = actuator(28, HEAD_GROUP)
    EYELED_R = actuator(29, HEAD_GROUP)
    EYELED_G = actuator(30, HEAD_GROUP)
    EYELED_B = actuator(31, HEAD_GROUP)

    @classmethod
    def get_ids_belonging_to_group(cls, group: str) -> list[int]:
        return [
            attr.id
            for attr in vars(cls).values()
            if isinstance(attr, actuator) and attr.group == group
        ]