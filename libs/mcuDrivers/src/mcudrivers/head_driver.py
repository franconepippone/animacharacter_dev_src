from typing import overload, Literal
import time
import math
import logging
from enum import Enum, auto
from threading import RLock
import struct

from pySerialDevice import SerialDevice
from .utils import *
from .base_driver import BaseHardwareDriver, GenericLogger


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
# - Neck right and left are derived from neck_pitch and neck_tilt
# - All multi-byte int16 fields are little-endian in the packet.


# ================= PACKET IDS =================

PACK_ID_MOTION = 0x10
PACK_ID_LEDS = 0x09
PACK_ID_CONTROL = 0x07

PSP_INIT_HARDWARE = bytes([1])
PSP_DEINIT = bytes([2])
PSP_BEGIN_ALL = bytes([4])

# ================= EXCEPTIONS

class InvalidAxis(Exception): ...


# ================= ENUMS =================

class Axis(Enum):
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
    UNKNOWN_AXIS = -2



# ================= DRIVER =================

class HeadMcuDriver(BaseHardwareDriver):
    """
    Animatronic head MCU driver.
    Current status is sent to hardware via flush().

    This class is already thread safe, meaning that different threads can
    write and flush concurrently without causing data corruption, but NOTE:   
    by default, each call to write acquires and releases the lock; this can result in overhead if done at high
    frequency. If you are writing to multiple axis, it's recommended to use the
    'batch_write_lock()' method called within a context manager to acquire and the release the lock once,
    and perform writing inside the context.
    """
    
    # -------- constants --------
    class CFG:
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

    # set for quick membership checks
    _LED_AXIS = frozenset({Axis.LED_R, Axis.LED_G, Axis.LED_B, Axis.LED_L1, Axis.LED_L2})

    def __init__(self, serial_port: str, logger: GenericLogger | None = None):
        """
        Initialize the Head MCU Driver.
        
        Args:
            serial_port: Serial port path (e.g., '/dev/ttyUSB0').
        """
        self.logger = logger
        self.esp32 = SerialDevice(
            self.CFG._DEFAULT_NAME,
            serial_port,
            self.CFG._DEFAULT_BAUDRATE
        )

        # lock for thread safe access
        self._lock = RLock()

        # precompiled packer for motion packets (mp) and leds packet
        self.mp_packer = struct.Struct("<BBBBBhhhhh")
        self.leds_packer = struct.Struct("<hhhhh")

        # buffers for packets
        self.motionpack_buffer = bytearray(15)
        self.ledspack_buffer = bytearray(10)

        # signals wheter or not there is any
        # pending update to flush
        self._mp_dirty = False
        self._leds_dirty = False

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
        if name != self.CFG._DEVICE_NAME:
            return False

        self.esp32.send_object(PSP_INIT_HARDWARE, PACK_ID_CONTROL)
        if not self.esp32.wait_packet(10):
            return False

        time.sleep(0.25)
        self.esp32.send_object(PSP_BEGIN_ALL, PACK_ID_CONTROL)
        time.sleep(0.25)

        self.flush()
        logging.info("[AnimaHead] Hardware initialized.")
        return True

    def deinit(self) -> bool:
        """Deinitialize hardware and close connection."""
        self.esp32.send_object(PSP_DEINIT, PACK_ID_CONTROL)
        self.esp32.close()
        return True

    def _mark_dirty(self, axis: Axis):
        was_led_updt = axis in self._LED_AXIS
        self._leds_dirty |= was_led_updt
        self._mp_dirty |= not was_led_updt

    def _write_axis(self, axis: Axis, val):
        match axis:
            # ---- LEDs ----
            case Axis.LED_R: self.led_r = topwm12(val)
            case Axis.LED_G: self.led_g = topwm12(val)
            case Axis.LED_B: self.led_b = topwm12(val)
            case Axis.LED_L1: self.led_l1 = topwm8(val)
            case Axis.LED_L2: self.led_l2 = topwm8(val)
            # ---- Mouth / ears ----
            case Axis.MOUTH: self.mouth = clamp(val, 0, 1)
            case Axis.EAR_L: self.ear_left = clamp(val, -1, 1)
            case Axis.EAR_R: self.ear_right = clamp(val, -1, 1)
            # ---- Neck (virtual) ----
            case Axis.NECK_TILT: self.neck_tilt = clamp(val, -1, 1)
            case Axis.NECK_PITCH: self.neck_pitch = clamp(val, -1, 1)
            # ---- Eyes ----
            case Axis.EYE_L: self.eye_left = clamp(val, -self.CFG._EYE_YAW_RANGE_DEG, self.CFG._EYE_YAW_RANGE_DEG)
            case Axis.EYE_R: self.eye_right = clamp(val, -self.CFG._EYE_YAW_RANGE_DEG, self.CFG._EYE_YAW_RANGE_DEG)
            case Axis.EYES_PITCH: self.eyes_pitch = clamp(val, -self.CFG._EYE_PITCH_RANGE_DEG, self.CFG._EYE_PITCH_RANGE_DEG)
            # ---- Lids ----
            case Axis.LID_L: self.lid_left_wideness = clamp(val * 0.5, 0, self.CFG._LID_WIDENESS_MAX_DEG)
            case Axis.LID_R: self.lid_right_wideness = clamp(val * 0.5, 0, self.CFG._LID_WIDENESS_MAX_DEG)
            case Axis.EYES_OPEN: self.eyes_open = float(bool(val))
            # unknown
            case _: raise InvalidAxis(axis)
        
        self._mark_dirty(axis)

    # ================= PUBLIC API =================

    def batch_write_lock(self) -> RLock:
        """Use this lock of inside a context manager for batch writing using
        only one lock acquisition.
        """
        # equivalent to just acquiring self._lock
        return self._lock

    @overload
    def write(self, axis: Literal[Axis.EYES_OPEN], val: bool) -> WriteOutcome: ...
    @overload
    def write(self, axis: Axis, val: float) -> WriteOutcome: ...

    def write(self, axis: Axis, val) -> WriteOutcome:
        """
        Write value to an axis/actuator.
        
        Args:
            axis: Axis/actuator to update (from Axis enum).
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
            WriteOutcome enum: OK, ERROR, or UNKNOWN_AXIS.
        """
        try:
            # only acquire lock if not already locked by batch context manager
            with self._lock:
                self._write_axis(axis, val)
            return WriteOutcome.OK
        except InvalidAxis:
            return WriteOutcome.UNKNOWN_AXIS
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
        self.write(Axis.NECK_TILT, tilt)
        self.write(Axis.NECK_PITCH, pitch)

    def set_eyes(self, pitch: float, yaw_left: float, yaw_right: float):
        """
        Set eye position (pitch and yaw for each eye).
        
        Args:
            pitch: [-30, 30] degrees vertical eye rotation.
            yaw_left: [-60, 60] degrees left eye horizontal rotation.
            yaw_right: [-60, 60] degrees right eye horizontal rotation.
        """
        self.write(Axis.EYES_PITCH, pitch)
        self.write(Axis.EYE_L, yaw_left)
        self.write(Axis.EYE_R, yaw_right)

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

        # TODO to be implemented
        raise NotImplementedError()

    def set_eyelids(self, left: float, right: float):
        """
        Set eyelid wideness.
        
        Args:
            left: [0, 1] where 0=fully closed, 1=fully open.
            right: [0, 1] where 0=fully closed, 1=fully open.
        """
        with self._lock:
            self.write(Axis.LID_L, left)
            self.write(Axis.LID_R, right)

    def set_mouth(self, value: float):
        """Set mouth aperture: 0 = fully open, 1 = fully closed."""
        self.write(Axis.MOUTH, value)

    def set_left_ear(self, value: float):
        """Set left ear: -1 fully forward, 0 neutral, 1 fully backward."""
        self.write(Axis.EAR_L, value)

    def set_right_ear(self, value: float):
        """Set right ear: -1 fully forward, 0 neutral, 1 fully backward."""
        self.write(Axis.EAR_R, value)

    def set_lid_left(self, value: float):
        """Set left eyelid aperture (degrees, scaled internally)."""
        self.write(Axis.LID_L, value)

    def set_lid_right(self, value: float):
        """Set right eyelid aperture (degrees, scaled internally)."""
        self.write(Axis.LID_R, value)

    def set_eyes_closed(self, closed: bool):
        """Close or open both eyes."""
        self.write(Axis.EYES_OPEN, not closed)

    def set_rgb(self, r: float, g: float, b: float):
        """Set RGB LED channels (0..1)."""
        with self._lock:
            self.write(Axis.LED_R, r)
            self.write(Axis.LED_G, g)
            self.write(Axis.LED_B, b)

    def set_iris_leds(self, l1: float, l2: float):
        """Set iris LEDs brightness (0..1)."""
        with self._lock:
            self.write(Axis.LED_L1, l1)
            self.write(Axis.LED_L2, l2)

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
            semi_IPDmm = self.CFG._SEMI_IPDmm

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

    def flush(self) -> bool:
        """
        Flush all pending updates to hardware via serial communication.
        Sends motion packet (servos) and LED updates if changes were made.

        Returns True if serial transmission occurred and was successfull.
        """
        
        if not self._mp_dirty and not self._leds_dirty:
            return False

        cfg = self.CFG
        # compute tranformations for neck
        neck_left_mot = int(cfg._NECK_L_OFFSET - self.neck_tilt * cfg._NECK_TILT_SCALE + self.neck_pitch * cfg._NECK_PITCH_SCALE)
        neck_right_mot = int(cfg._NECK_R_OFFSET + self.neck_tilt * cfg._NECK_TILT_SCALE + self.neck_pitch * cfg._NECK_PITCH_SCALE)

        with self._lock:
            # costruct packets into buffers
            try:
                if self._mp_dirty:
                    self.mp_packer.pack_into(self.motionpack_buffer, 0, 
                        int(self.mouth * cfg._MOUTH_INPUT_SCALE),
                        int(self.ear_left * cfg._EARS_INPUT_SCALE),
                        int(self.ear_right * cfg._EARS_INPUT_SCALE),
                        int(self.lid_left_wideness * self.eyes_open),
                        int(self.lid_right_wideness * self.eyes_open),
                        int(self.eye_left),
                        int(self.eye_right),
                        int(self.eyes_pitch),
                        neck_left_mot,
                        neck_right_mot
                        )
                
                if self._leds_dirty:
                    self.leds_packer.pack_into(self.ledspack_buffer, 0,
                        self.led_r,
                        self.led_g,
                        self.led_b,
                        self.led_l1,
                        self.led_l2
                    )
            except struct.error as e:
                if self.logger: self.logger.error(f"Head Driver caught exception during packaging phase of 'flush': {e}")
                return False
        
        # I/O - flush to hardware
        try:
            success = True
            if self._mp_dirty:
                success = self.esp32.send_object(self.motionpack_buffer, PACK_ID_MOTION)
                if success: self._mp_dirty = False # if send fails, keep flag to dirty

            if self._leds_dirty:
                success_led = self.esp32.send_object(self.ledspack_buffer, PACK_ID_LEDS)
                if success_led: self._leds_dirty = False # if send fails, keep flag to dirty
                success = success and success_led # success only if both succeed

            if not success and self.logger: self.logger.warning("Serial packet transmission failed.")
            return success
        
        except Exception as e:
            if self.logger: self.logger.error(f"Head Driver caught exception during I/O phase of 'flush': {e}")
            return False