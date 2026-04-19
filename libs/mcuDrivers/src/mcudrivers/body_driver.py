import time
from pySerialDevice import SerialDevice
from mcudrivers.constants import *
import struct


class BodyMcuDriver:

    class CFG:
        OWN_NAME = 'master'
        PEER_NAME = 'AC01:BODY'

        BAUDRATE = 115200

    def __init__(self, serial_port: str):
        """
        Initialize the Head MCU Driver.
        
        Args:
            serial_port: Serial port path (e.g., '/dev/ttyUSB0').
        """
        self.initialized: bool = False
        self.dev = SerialDevice(
            self.CFG.OWN_NAME,
            serial_port,
            self.CFG.BAUDRATE
        )

        self.packer = struct.Struct("<hhh")
        self.payload_buffer = bytearray(6)

        # state

        self.left_mot: int = 0
        self.right_mot: int = 0
        self.rotation_mot: int = 0

    def begin(self) -> bool:
        """
        Initialize hardware connection and put hardware in a ready-to-operate state.
        
        Returns:
            True if initialization successful, False otherwise.
        """
        if self.initialized: return True

        if not self.dev.open(1): 
            print("Could not open serial device")
            return False

        time.sleep(2) # needed for arduino nano
        
        name = self.dev.request_peername(5)
        if name != self.CFG.PEER_NAME:
            print(f"Serial device not match expected name: got {name} instead of {self.CFG.PEER_NAME}")
            return False

        self.dev.send_object(INIT_HARDWARE, PSP_PACKID_CONTROL_FLAGS)
        if not (p := self.dev.wait_packet(5)):
            print(f"Failed to received ack packet after hardware init request")
            return False
        
        if not (p.id == PSP_PACKID_DIAGNOSTICS and p.data == DGN_HARDWARE_INIT_OK):
            print(f"Failed to initialize hardware")
            return False 

        time.sleep(.5)
        self.dev.send_object(BEGIN_ALL, PSP_PACKID_CONTROL_FLAGS)
        time.sleep(.5)

        if not (p := self.dev.wait_packet(5)):
            print("Timed out")
            return False
            
        if not (p.id == PSP_PACKID_DIAGNOSTICS and p.data == DGN_BEGINALL_OK):
            print(f"Failed to startup hardware (beginall failed)")
            return False

        print("Hardware initialized.")
        self.initialized = True
        return True

    def deinit(self) -> bool:
        """Deinitialize hardware and close connection."""
        if not self.initialized: return True # dont if we are still deinitialized

        if not self.dev.send_object(DEINIT_HARDWARE, PSP_PACKID_CONTROL_FLAGS):
            print("Could not send deinit request to serial device, closing anyway...")
            return False
        if not (p := self.dev.wait_packet(5)):
            print("Deinit ack timed out")
            return False
        if not (p.id == PSP_PACKID_DIAGNOSTICS and p.data == DGN_HARDWARE_DEINIT_ACK):
            print("Invalid deinit ack")
            return False
         
        self.dev.close()
        self.initialized = False
        print("deinit ok!")
        return True

    def isinit(self) -> bool:
        return self.initialized


    def flush(self) -> bool:
        self.packer.pack_into(self.payload_buffer, 0, self.right_mot, self.left_mot, self.rotation_mot)
        return self.dev.send_object(self.payload_buffer, PSP_PACKID_MOTION)

    


driver = BodyMcuDriver('COM3')
driver.begin()

import random
import math
for _ in range(100):
    driver.rotation_mot = random.randint(-5000, 5000)
    driver.flush()
    time.sleep(.2)

driver.deinit()