from typing import Tuple, Callable
import time
import math
import logging

from pySerialDevice import SerialDevice

from .utils import *

# Serial packet ids
PACK_ID_MOTION = 0x10
PACK_ID_LEDS = 0x9
PACK_ID_CONTROL = 0x07
PACK_ID_MOTION_PARAMETERS = 0x08
PACK_ID_DIAGNOSTIC = 0x05

# Control flags 
PSP_INIT_HARDWARE = bytes([1])
PSP_DEINIT = bytes([2])
PSP_BEGIN_ALL = bytes([4])



class HeadMcuDriver:
    """
    Handles interactions with the animatronic head.
    Hardware will only update upon calling the "drive_hardware()" method. Refer to the specific methods docstring for usage.
    Call "begin()" to initialize, "deinit()" to stop everything (turns all motors off).
    """
    # configs
    _RGB_MAX_DUTY = 4095
    _RINGLED_MAX_DUTY = 255
    _MOUTH_INPUT_SCALE = 255
    _EARS_INPUT_SCALE = 127
    _NECK_PITCH_SCALE = 50
    _NECK_TILT_SCALE = 35
    _NECK_L_OFFSET = 150
    _NECK_R_OFFSET = 270
    _SEMI_IPDmm = 75 # half of inter pupillar distance in mm

    _DEFAULT_BAUDRATE = 115200
    _DEFAULT_NAME = "master"    # our serial device name

    def __init__(self, serial_port: str):
        self.esp32 = SerialDevice(self._DEFAULT_NAME, serial_port, self._DEFAULT_BAUDRATE)
        self.motionpack_buffer = bytearray(15) # total size of motionpack_buffer
        self.mp_buff_mv = memoryview(self.motionpack_buffer)

        # flags
        self._updt_leds: bool = True
        self._updt_servos: bool = True

        # state variables
        self.led_r: int = 0
        self.led_g: int = 0
        self.led_b: int = 0
        self.led_l1: int = 0
        self.led_l2: int = 0

        self.mouth: float = 1.0
        self.ear_left: float = 0.0
        self.ear_right: float = 0.0
        self.neck_left: float = self._NECK_L_OFFSET #neck servos hold raw values
        self.neck_right: float = self._NECK_R_OFFSET

        self.eyes_pitch: float = 0.0
        self.eye_left: float = 0.0
        self.eye_right: float = 0.0
        self.lid_left_wideness: float = 20.0
        self.lid_right_wideness: float = 20.0
        self.eyes_open: int = 1

    def begin(self) -> bool:
        """Wakes up hardware and gets the device ready to receive commands."""
        self.esp32.open(1)

        name = self.esp32.request_peername(5)
        if name != "TEODORE:api-v0a:HEAD":    # we check if the mcu supports this api
            # we should set some internal status flags, so we can trace errors
            return False

        self.esp32.send_object(PSP_INIT_HARDWARE, PACK_ID_CONTROL)
        if not (p := self.esp32.wait_packet(10)): #, allowed_ids=[PACK_ID_CONTROL_RESP]
            # we should send a response back ideally
            return False
        time.sleep(.5)
        self.esp32.send_object(PSP_BEGIN_ALL, PACK_ID_CONTROL)
        time.sleep(.25)
        self.drive_hardware()
        time.sleep(.25)
        logging.info("[AnimaHead] Hardware initialized.")
        return True
    
    def deinit(self):
        """Sends a deinitialization command to the esp32. This is equivalent to power cycling the mcu."""
        self.esp32.send_object(PSP_DEINIT, PACK_ID_CONTROL)
        # TODO maybe add a response here to, to see if command was received

    def set_rgb(self, r: float, g: float, b: float):
        """Sets rgb channels values from 0 (fully off) to 1 (fully on)."""
        self._set_rgb_raw(int(remap(r, self._RGB_MAX_DUTY)), 
                         int(remap(g, self._RGB_MAX_DUTY)), 
                         int(remap(b, self._RGB_MAX_DUTY)))
    
    def get_rgb(self) -> Tuple[float, float, float]:
        """Returns current state of rgb leds."""
        return self.led_r / self._RGB_MAX_DUTY, self.led_g / self._RGB_MAX_DUTY, self.led_b / self._RGB_MAX_DUTY

    def _set_rgb_raw(self, r: int, g: int, b: int):
        "Sets rgb channels duty cycle from 0 to 4095."
        self.led_r = r
        self.led_g = g
        self.led_b = b
        self._updt_leds = True
    
    def set_iris_leds(self, l1: float, l2: float):
        """Sets brightness of iris leds from 0 to 1"""
        self._set_iris_leds_raw(int(remap(l1, self._RINGLED_MAX_DUTY)), int(remap(l2, self._RINGLED_MAX_DUTY)))
        self._updt_leds = True

    def _set_iris_leds_raw(self, l1: int, l2: int):
        """Sets duty cycle from 0 to 255."""
        self.led_l1 = l1
        self.led_l2 = l2
        self._updt_leds = True

    def fade(self, function, args: list[float], time: float):
        """Takes in a function and linearly iterpolates to value in time seconds"""
        ...

    def set_mouth(self, value: float):
        "Value must be in range 0 (fully open) to 1 (fully closed)"
        self.mouth = min(max(value, 0), 1.0)
        # write value directyto packet buffer
        self.mp_buff_mv[0:1] = to_uint8(self.mouth * self._MOUTH_INPUT_SCALE) 
        self._updt_servos = True

    def set_left_ear(self, value: float):
        """Value must be in range -1 (fully forward) to 1 (fully backwards). 0 is perfectly straight."""
        self.ear_left = min(max(value, -1.0), 1.0)
        self.mp_buff_mv[1:2] = to_uint8(self.ear_left * self._EARS_INPUT_SCALE)
        self._updt_servos = True

    def set_right_ear(self, value: float):
        """Value must be in range -1 (fully forward) to 1 (fully backwards). 0 is perfectly straight."""
        self.ear_right = min(max(value, -1.0), 1.0)
        self.mp_buff_mv[2:3] =  to_uint8(self.ear_right * self._EARS_INPUT_SCALE)
        self._updt_servos = True

    def set_neck_rotation(self, tilt: float, pitch: float):
        """Values must be in range -1 to 1; 0 is straight."""
        self.neck_left = self._NECK_L_OFFSET - tilt * self._NECK_TILT_SCALE + pitch * self._NECK_PITCH_SCALE
        self.neck_right = self._NECK_R_OFFSET + tilt * self._NECK_TILT_SCALE + pitch * self._NECK_PITCH_SCALE
        self.mp_buff_mv[11:13] = to_int16(self.neck_right)
        self.mp_buff_mv[13:15] =  to_int16(self.neck_left)
        self._updt_servos = True
    
    def set_eyes(self, pitch: float, yaw_left: float, yaw_right: float):
        """Values represent angle (in degrees)."""
        self.eyes_pitch = min(max(pitch, -30), 30)
        self.eye_left = min(max(yaw_left, -60), 60)
        self.eye_right = min(max(yaw_right, -60), 60)
        # write to buffer
        self.mp_buff_mv[5:7] =  to_int16(self.eye_left)
        self.mp_buff_mv[7:9] =  to_int16(self.eye_right)
        self.mp_buff_mv[9:11] =  to_int16(self.eyes_pitch)
        self._updt_servos = True
    
    def lookat(self, elevation_ang: float, lateral_ang: float, r: float, semi_IPDmm: float = -1):
        """Look at a point at distance r (centimeters). Angles are in degrees."""
        if semi_IPDmm <= 0:
            semi_IPDmm = self._SEMI_IPDmm

        DEG_TO_RAD = math.radians(1)
        R = 10 * r
        yaw_left = math.degrees(1) * math.atan2(R * math.sin(lateral_ang * DEG_TO_RAD) - semi_IPDmm, R * math.cos(lateral_ang * DEG_TO_RAD))
        yaw_right = math.degrees(1) * math.atan2(R * math.sin(lateral_ang * DEG_TO_RAD) + semi_IPDmm, R* math.cos(lateral_ang * DEG_TO_RAD))
        self.set_eyes(elevation_ang, yaw_left, yaw_right)
        self._updt_servos = True

    def set_eyelids(self, aperture_left: float, aperture_right: float):
        """Value represent the angle (positive, in degrees) formed by a pair of eyelids (0 is closed)"""
        self.lid_left_wideness = min(max(aperture_left * 0.5, 0), 60)
        self.lid_right_wideness = min(max(aperture_right * 0.5, 0), 60)
        self.mp_buff_mv[3:4] =  to_uint8(self.lid_left_wideness * self.eyes_open)
        self.mp_buff_mv[4:5] =  to_uint8(self.lid_right_wideness * self.eyes_open)
        self._updt_servos = True

    def set_eyes_closed(self, closed: bool):
        self.eyes_open = int(not closed)
        # update memory
        self.mp_buff_mv[3:4] =  to_uint8(self.lid_left_wideness * self.eyes_open)
        self.mp_buff_mv[4:5] =  to_uint8(self.lid_right_wideness * self.eyes_open)
        self._updt_servos = True
    
    def drive_hardware(self):
        """Updates the hardware with the current axys configuration. May raise serial exceptions.
        """
        # if there has been a servo update
        # 8 + 8 + 8 + 8 + 8 + 16 + 16 + 16 + 16 + 16 bits = 15 byte packet
        if self._updt_servos:

            #packet_data = to_uint8(self.mouth * self._MOUTH_INPUT_SCALE)
            #packet_data += to_int8(self.ear_left * self._EARS_INPUT_SCALE) + to_int8(self.ear_right * self._EARS_INPUT_SCALE)
            #packet_data += to_uint8(self.lid_left_wideness * self.eyes_open) + to_uint8(self.lid_right_wideness * self.eyes_open)
            #packet_data += to_int16(self.eye_left) + to_int16(self.eye_right) + to_int16(self.eyes_pitch)
            #packet_data += to_int16(self.neck_right) + to_int16(self.neck_left)
            
            # we dont need to write any data, it's already it the buffer
            self.esp32.send_object(self.mp_buff_mv, PACK_ID_MOTION) # sends packet to esp32 over serial
            self._updt_servos = False

        # if there has been a leds update
        if self._updt_leds:
            # TODO turn this into a single byte, we are just wasting bandwith
            data = to_uint16(self.led_r) + to_uint16(self.led_g) + to_uint16(self.led_b)
            data += to_uint16(self.led_l1) + to_uint16(self.led_l2)
            
            self.esp32.send_object(data, PACK_ID_LEDS) # sends packet to esp32 over serial
            self._updt_leds = False
