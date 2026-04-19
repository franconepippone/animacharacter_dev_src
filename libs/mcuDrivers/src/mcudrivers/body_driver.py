import time
from pySerialDevice import SerialDevice
from mcudrivers.constants import *

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

    def begin(self) -> bool:
        """
        Initialize hardware connection and synchronize with MCU.
        
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

        self.dev.send_object(PSP_INIT_HARDWARE, PACK_ID_CONTROL)
        #if not self.dev.wait_packet(5):
        #    print(f"Failed to received ack packet after hardware init request")
        #    return False

        time.sleep(.5)
        self.dev.send_object(PSP_BEGIN_ALL, PACK_ID_CONTROL)
        time.sleep(.5)

        #if not self.flush():
        #    print("Could not flush initial hardware state")
        #    return False
        
        print("Hardware initialized.")
        self.initialized = True
        return True

    def deinit(self) -> bool:
        """Deinitialize hardware and close connection."""
        if not self.initialized: return True # dont if we are still deinitialized

        if not self.dev.send_object(PSP_DEINIT, PACK_ID_CONTROL):
            print("Could not send deinit request to serial device, closing anyway...")
        self.dev.close()
        self.initialized = False
        return True

    def isinit(self) -> bool:
        return self.initialized
    


#driver = BodyMcuDriver('COM3')
#driver.begin()

dev = SerialDevice("peppe", 'COM3')
dev.open(1)
time.sleep(2)

name = dev.request_peername(5)
print(name)

dev.send_object(PSP_INIT_HARDWARE, PACK_ID_CONTROL)

while True:
    name = dev.request_peername(5)
    print(name)