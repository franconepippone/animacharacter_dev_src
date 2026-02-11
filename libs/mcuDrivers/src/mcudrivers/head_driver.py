from typing import overload, Literal, Tuple
import time
import math
import logging
from enum import Enum, auto
import zlib
from threading import Lock

from pySerialDevice import SerialDevice
from .utils import *
from .base_driver import BaseHardwareDriver


# ================= MOTION PACKET LAYOUT =================
#
# The motion packet sent to the MCU is exactly 15 bytes.
# Each byte or byte pair corresponds to a specific actuator.
# Multi-byte fields are stored as little-endian integers (16-bit).
#
# ┌─────────┬───────────────┬───────────────┬─────────────────────────────┐
# │ Bytes   │ Field         │ Type / Scale  │ Description                 │
# ├─────────┼───────────────┼───────────────┼─────────────────────────────┤
# │ 0       │ Mouth         │ uint8 0..255  │ 0 = fully open, 255 = closed│
# │ 1       │ Left Ear      │ uint8 0..127  │ -1..1 scaled to 0..127     │      <---- XXX CHECK THE EARS!!!!
# │ 2       │ Right Ear     │ uint8 0..127  │ -1..1 scaled to 0..127     │
# │ 3       │ Left Lid      │ uint8 0..60*  │ Lid wideness * eyes_open    │
# │ 4       │ Right Lid     │ uint8 0..60*  │ Lid wideness * eyes_open    │
# │ 5-6     │ Eye Left Yaw  │ int16         │ Degrees -60..60             │
# │ 7-8     │ Eye Right Yaw │ int16         │ Degrees -60..60             │
# │ 9-10    │ Eyes Pitch    │ int16         │ Degrees -30..30             │
# │ 11-12   │ Neck Right    │ int16         │ Computed from tilt/pitch    │
# │ 13-14   │ Neck Left     │ int16         │ Computed from tilt/pitch    │
# └─────────┴───────────────┴───────────────┴─────────────────────────────┘
#
# Notes:
# - Lid wideness is multiplied by eyes_open (0 or 1) to support blinking.
# - Neck servo values are derived:
#       left  = L_OFFSET - tilt*TILT_SCALE + pitch*PITCH_SCALE
#       right = R_OFFSET + tilt*TILT_SCALE + pitch*PITCH_SCALE
# - All multi-byte int16 fields are little-endian in the packet.
# - The packet is sent as a continuous bytearray (15 bytes).


# ================= PACKET IDS =================

PACK_ID_MOTION = 0x10
PACK_ID_LEDS = 0x09
PACK_ID_CONTROL = 0x07

PSP_INIT_HARDWARE = bytes([1])
PSP_DEINIT = bytes([2])
PSP_BEGIN_ALL = bytes([4])

# ================= EXCEPTIONS

class InvalidAxys(Exception): ...


# ================= ENUMS =================

class Axys(Enum):
    LED_R = auto()
    LED_G = auto()
    LED_B = auto()
    LED_L1 = auto()
    LED_L2 = auto()

    MOUTH = auto()
    EAR_L = auto()
    EAR_R = auto()
    NECK_PITCH = auto()
    NECK_TILT = auto()

    EYES_PITCH = auto()
    EYE_L = auto()
    EYE_R = auto()
    LID_L = auto()
    LID_R = auto()
    EYES_OPEN = auto()


class WriteOutcome(Enum):
    OK = 0
    ERROR = -1
    UNKNOWN_AXYS = -2


# ================= DRIVER =================

class HeadMcuDriver(BaseHardwareDriver):
    """
    Animatronic head MCU driver.
    All hardware updates are flushed via drive_hardware().

    This class is already thread-safe, meaning that write and drive methods can be called concurrently
    without causing data corruption.
    """

    # -------- constants --------

    _RGB_MAX_DUTY = 4095
    _RINGLED_MAX_DUTY = 255

    _EYE_YAW_RANGE_DEG = 60
    _EYE_PITCH_RANGE_DEG = 30
    _LID_WIDENESS_MAX_DEG = 60

    _MOUTH_INPUT_SCALE = 255
    _EARS_INPUT_SCALE = 127

    _NECK_PITCH_SCALE = 50
    _NECK_TILT_SCALE = 35
    _NECK_L_OFFSET = 150
    _NECK_R_OFFSET = 270

    _SEMI_IPDmm = 75

    _DEFAULT_BAUDRATE = 115200
    _DEFAULT_NAME = "master"
    _DEVICE_NAME =  "TEODORE:api-v0a:HEAD"

    # -------- init --------

    def __init__(self, serial_port: str):
        """
        Initialize the Head MCU Driver.
        
        Args:
            serial_port: Serial port path (e.g., '/dev/ttyUSB0').
        """
        self.esp32 = SerialDevice(
            self._DEFAULT_NAME,
            serial_port,
            self._DEFAULT_BAUDRATE
        )

        # lock for thread safe access
        self._lock = Lock()

        # motion packet: EXACTLY 15 BYTES
        self.motionpack_buffer = bytearray(15)
        self.mp_buff_mv = memoryview(self.motionpack_buffer)

        self._updt_leds = True
        self._updt_servos = True

        self._prev_buff_hash: int = 0

        # -------- logical state --------

        # leds
        self.led_r = 0
        self.led_g = 0
        self.led_b = 0
        self.led_l1 = 0
        self.led_l2 = 0

        # face / servos
        self.mouth = 1.0
        self.ear_left = 0.0
        self.ear_right = 0.0

        self.neck_tilt = 0.0
        self.neck_pitch = 0.0

        self.eye_left = 0.0
        self.eye_right = 0.0
        self.eyes_pitch = 0.0

        self.lid_left_wideness = 20.0
        self.lid_right_wideness = 20.0
        self.eyes_open = 1.0

    # ================= CONNECTION =================

    def begin(self) -> bool:
        """
        Initialize hardware connection and synchronize with MCU.
        
        Returns:
            True if initialization successful, False otherwise.
        """
        self.esp32.open(1)

        name = self.esp32.request_peername(5)
        if name != self._DEVICE_NAME:
            return False

        self.esp32.send_object(PSP_INIT_HARDWARE, PACK_ID_CONTROL)
        if not self.esp32.wait_packet(10):
            return False

        time.sleep(0.25)
        self.esp32.send_object(PSP_BEGIN_ALL, PACK_ID_CONTROL)
        time.sleep(0.25)

        self.drive_hardware()
        logging.info("[AnimaHead] Hardware initialized.")
        return True

    def deinit(self) -> bool:
        """Deinitialize hardware and close connection."""
        self.esp32.send_object(PSP_DEINIT, PACK_ID_CONTROL)
        self.esp32.close()
        return True

    # ================= PRIVATE PROJECTIONS =================

    # bytes 11–14
    def _apply_neck_to_buffer(self):
        """Apply current neck_tilt and neck_pitch values to motion packet buffer."""
        # computes motor angles based on tilt and pitch
        left = self._NECK_L_OFFSET - self.neck_tilt * self._NECK_TILT_SCALE + self.neck_pitch * self._NECK_PITCH_SCALE    
        right = self._NECK_R_OFFSET + self.neck_tilt * self._NECK_TILT_SCALE + self.neck_pitch * self._NECK_PITCH_SCALE
        self.mp_buff_mv[11:13] = to_int16(right)
        self.mp_buff_mv[13:15] = to_int16(left)

    # bytes 3–4
    def _apply_lids_to_buffer(self):
        """Apply current lid wideness and eyes_open values to motion packet buffer."""
        self.mp_buff_mv[3:4] = to_uint8(self.lid_left_wideness * self.eyes_open)
        self.mp_buff_mv[4:5] = to_uint8(self.lid_right_wideness * self.eyes_open)

    # ================= AXIS WRITE CORE =================

    def _has_mp_updated(self) -> bool:
        """
        Returns True if the motion packet buffer has changed since the last call.
        Updates the stored hash when a change is detected.
        """
        new_hash = zlib.crc32(self.mp_buff_mv) & 0xffffffff
        if new_hash != self._prev_buff_hash:
            self._prev_buff_hash = new_hash
            return True
        return False

    def _write_axis(self, axys: Axys, val):
        match axys:

            # ---- LEDs ----
            case Axys.LED_R:
                self.led_r = topwm12(val)
                self._updt_leds = True

            case Axys.LED_G:
                self.led_g = topwm12(val)
                self._updt_leds = True

            case Axys.LED_B:
                self.led_b = topwm12(val)
                self._updt_leds = True

            case Axys.LED_L1:
                self.led_l1 = topwm8(val)
                self._updt_leds = True

            case Axys.LED_L2:
                self.led_l2 = topwm8(val)
                self._updt_leds = True

            # ---- Mouth / ears ----
            case Axys.MOUTH:
                self.mouth = clamp(val, 0, 1)
                self.mp_buff_mv[0:1] = to_uint8(self.mouth * self._MOUTH_INPUT_SCALE)

            case Axys.EAR_L:
                self.ear_left = clamp(val, -1, 1)
                self.mp_buff_mv[1:2] = to_uint8(self.ear_left * self._EARS_INPUT_SCALE)

            case Axys.EAR_R:
                self.ear_right = clamp(val, -1, 1)
                self.mp_buff_mv[2:3] = to_uint8(self.ear_right * self._EARS_INPUT_SCALE)

            # ---- Neck (derived) ----
            case Axys.NECK_TILT:
                self.neck_tilt = clamp(val, -1, 1)
                self._apply_neck_to_buffer()

            case Axys.NECK_PITCH:
                self.neck_pitch = clamp(val, -1, 1)
                self._apply_neck_to_buffer()

            # ---- Eyes ----
            case Axys.EYE_L:
                self.eye_left = clamp(val, -self._EYE_YAW_RANGE_DEG, self._EYE_YAW_RANGE_DEG)
                self.mp_buff_mv[5:7] = to_int16(self.eye_left)

            case Axys.EYE_R:
                self.eye_right = clamp(val, -self._EYE_YAW_RANGE_DEG, self._EYE_YAW_RANGE_DEG)
                self.mp_buff_mv[7:9] = to_int16(self.eye_right)

            case Axys.EYES_PITCH:
                self.eyes_pitch = clamp(val, -self._EYE_PITCH_RANGE_DEG, self._EYE_PITCH_RANGE_DEG)
                self.mp_buff_mv[9:11] = to_int16(self.eyes_pitch)

            # ---- Lids ----
            case Axys.LID_L:
                self.lid_left_wideness = clamp(val * 0.5, 0, self._LID_WIDENESS_MAX_DEG)
                self._apply_lids_to_buffer()

            case Axys.LID_R:
                self.lid_right_wideness = clamp(val * 0.5, 0, self._LID_WIDENESS_MAX_DEG)
                self._apply_lids_to_buffer()

            case Axys.EYES_OPEN:
                self.eyes_open = float(bool(val))
                self._apply_lids_to_buffer()

            case _:
                raise InvalidAxys(axys)

    # ================= PUBLIC API =================

    @overload
    def write(self, axys: Literal[Axys.EYES_OPEN], val: bool) -> WriteOutcome: ...
    @overload
    def write(self, axys: Axys, val: float) -> WriteOutcome: ...

    def write(self, axys: Axys, val) -> WriteOutcome:
        """
        Write value to an axis/actuator.
        
        Args:
            axys: Axis/actuator to update (from Axys enum).
            val: Value to set:
                - MOUTH: [0, 1] where 0=fully open, 1=fully closed.
                - EAR_L/EAR_R: [-1, 1] where -1=back, 0=neutral, 1=forward.
                - NECK_TILT: [-1, 1] where -1=left, 0=center, 1=right.
                - NECK_PITCH: [-1, 1] where -1=down, 0=center, 1=up.
                - EYE_L/EYE_R: [-60, 60] degrees yaw.
                - EYES_PITCH: [-30, 30] degrees pitch.
                - LID_L/LID_R: [0, 1] where 0=fully closed, 1=fully open.
                - EYES_OPEN: bool, whether eyes are open (blink control).
                - LED_R/LED_G/LED_B: [0, 1] for RGB brightness.
                - LED_L1/LED_L2: [0, 1] for ring LED brightness.
        
        Returns:
            WriteOutcome enum: OK, ERROR, or UNKNOWN_AXYS.
        """
        try:
            with self._lock:
                self._write_axis(axys, val)
            return WriteOutcome.OK
        except InvalidAxys:
            return WriteOutcome.UNKNOWN_AXYS
        except Exception:
            return WriteOutcome.ERROR

    # ---- semantic helpers ----

    def set_neck_rotation(self, tilt: float, pitch: float):
        """
        Set neck rotation in both tilt and pitch.
        
        Args:
            tilt: [-1, 1] where -1=left, 0=center, 1=right.
            pitch: [-1, 1] where -1=down, 0=center, 1=up.
        """
        self.write(Axys.NECK_TILT, tilt)
        self.write(Axys.NECK_PITCH, pitch)

    def set_eyes(self, pitch: float, yaw_left: float, yaw_right: float):
        """
        Set eye position (pitch and yaw for each eye).
        
        Args:
            pitch: [-30, 30] degrees vertical eye rotation.
            yaw_left: [-60, 60] degrees left eye horizontal rotation.
            yaw_right: [-60, 60] degrees right eye horizontal rotation.
        """
        self.write(Axys.EYES_PITCH, pitch)
        self.write(Axys.EYE_L, yaw_left)
        self.write(Axys.EYE_R, yaw_right)

    def set_eyes_h(self, focus: float, angle: float):
        """
        Docstring for set_eyes_h
        
        :param self: Description
        :param focus: Description
        :type focus: float
        :param angle: Description
        :type angle: float
        :return: Description
        :rtype: bool
        """

    def set_eyelids(self, left: float, right: float):
        """
        Set eyelid wideness.
        
        Args:
            left: [0, 1] where 0=fully closed, 1=fully open.
            right: [0, 1] where 0=fully closed, 1=fully open.
        """
        self.write(Axys.LID_L, left)
        self.write(Axys.LID_R, right)

    def set_mouth(self, value: float):
        """Set mouth aperture: 0 = fully open, 1 = fully closed."""
        self.write(Axys.MOUTH, value)

    def set_left_ear(self, value: float):
        """Set left ear: -1 fully forward, 0 neutral, 1 fully backward."""
        self.write(Axys.EAR_L, value)

    def set_right_ear(self, value: float):
        """Set right ear: -1 fully forward, 0 neutral, 1 fully backward."""
        self.write(Axys.EAR_R, value)

    def set_lid_left(self, value: float):
        """Set left eyelid aperture (degrees, scaled internally)."""
        self.write(Axys.LID_L, value)

    def set_lid_right(self, value: float):
        """Set right eyelid aperture (degrees, scaled internally)."""
        self.write(Axys.LID_R, value)

    def set_eyes_closed(self, closed: bool):
        """Close or open both eyes."""
        self.write(Axys.EYES_OPEN, not closed)

    def set_rgb(self, r: float, g: float, b: float):
        """Set RGB LED channels (0..1)."""
        self.write(Axys.LED_R, r)
        self.write(Axys.LED_G, g)
        self.write(Axys.LED_B, b)

    def set_iris_leds(self, l1: float, l2: float):
        """Set iris LEDs brightness (0..1)."""
        self.write(Axys.LED_L1, l1)
        self.write(Axys.LED_L2, l2)

    def lookat(self, elevation_ang: float, lateral_ang: float, r: float, semi_IPDmm: float = -1):
        """
        Make the head look at a target point in space.
        
        Args:
            elevation_ang: Vertical angle in degrees.
            lateral_ang: Horizontal angle in degrees.
            r: Distance to target (in decimeters).
            semi_IPDmm: Half interpupillary distance in mm. Defaults to 75 mm if <= 0.
        """
        if semi_IPDmm <= 0:
            semi_IPDmm = self._SEMI_IPDmm

        DEG = math.radians(1)
        R = 10 * r

        yaw_left = math.degrees(
            math.atan2(
                R * math.sin(lateral_ang * DEG) - semi_IPDmm,
                R * math.cos(lateral_ang * DEG)
            )
        )
        yaw_right = math.degrees(
            math.atan2(
                R * math.sin(lateral_ang * DEG) + semi_IPDmm,
                R * math.cos(lateral_ang * DEG)
            )
        )

        self.set_eyes(elevation_ang, yaw_left, yaw_right)

    # ================= FLUSH =================

    def drive_hardware(self) -> bool:
        """
        Flush all pending updates to hardware via serial communication.
        Sends motion packet (servos) and LED updates if changes were made.

        Returns True if serial transmission was successfull.
        """
        data = b'' # needed for typehints

        with self._lock:
            succ = True
            if self._has_mp_updated():
                # XXX look at the commented snippet below
                succ = self.esp32.send_object(self.mp_buff_mv, PACK_ID_MOTION)

            if self._updt_leds:
                data = (
                    to_uint16(self.led_r)
                    + to_uint16(self.led_g)
                    + to_uint16(self.led_b)
                    + to_uint16(self.led_l1)
                    + to_uint16(self.led_l2)
                )
        
        if self._updt_leds:
            succ = succ and self.esp32.send_object(data, PACK_ID_LEDS)
            self._updt_leds = False

        return succ
    
        # WE CAN SNAPSHOT DATA TO DO THE IO OUTSIDE THE LOCK, THIS REQUIRES AD ADDITIONAL COPY,
        # BUT MIGHT BE WORTH IT IF IO BLOCKS FOR A LOT OF TIME
        """
        with self._lock:
            mp_changed = self._has_mp_updated()
            updt_leds = self._updt_leds

            # snapshot data needed for IO
            if mp_changed:
                motion = bytes(self.mp_buff_mv)  # or a view if your API allows
            if updt_leds:
                led_data = (
                    to_uint16(self.led_r)
                    + to_uint16(self.led_g)
                    + to_uint16(self.led_b)
                    + to_uint16(self.led_l1)
                    + to_uint16(self.led_l2)
                )
                self._updt_leds = False

        # do the slow IO *outside* the lock
        succ = True
        if mp_changed:
            succ = self.esp32.send_object(motion, PACK_ID_MOTION)
        if updt_leds:
            succ = succ and self.esp32.send_object(led_data, PACK_ID_LEDS)
        return succ
    """