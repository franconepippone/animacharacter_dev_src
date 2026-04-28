from typing import Dict, Callable, Any, Tuple, Optional
from collections.abc import Iterable
from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand
import socket
import select
import struct

class PeerUDP:
    """Simple UDP peer class to send packets to a peer
    """

    def __init__(self, peer_addr: Tuple[str, int]):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("", 0))
        #self.s.setblocking(True)

        self.host_addr = self.s.getsockname()
        self.peer_addr = peer_addr

    def send(self, packet: bytes) -> None:
        #print("sending", packet, "to", self.peer_addr)
        self.s.sendto(packet, self.peer_addr)

    def recv(self, timeout: float = 0) -> Optional[bytes]:
        # Wait for readability
        ready, _, _ = select.select([self.s], [], [], timeout)
        if not ready:
            return None

        try:
            packet, addr = self.s.recvfrom(2048)
        except BlockingIOError:
            return None

        if addr == self.peer_addr:
            return packet

        return None


# found address by running iside WSL:
# ip route show | grep -i default | awk '{ print $3}'
SIMULATOR_ADDRESS = "172.26.32.1", 500

PACKID_MOTION = b'\x00'
PACKID_PING = b'\x01'

class BaseControllerSim(BaseHardwareController):
    """This controller is used to interface with a local/remote hardware simulator.
    This just encodes and forwards the motion commands dispatched by the Hardware Manager as udp packets to the simulator.
    A compatible simulator can be found at `src/robot-sim3D`.
    """
    
    def __init__(self, name: str = "sim-bridge-controller"):
        super().__init__(name, flush_freq=30.0)
        self.subscribe_to_command_group([i for i in range(100)]) # make sure we are subscribing to everything
        self.subscribe_to_config_path('hello/there/test', self.config_test_handler)
        self.subscribe_to_config_path('hello/', self.config_test_handler)
        self.subscribe_to_config_path('/simple/', self.config_test_handler)

        # PUBLISH FAKE CONFIG UPDATES ON CLI:
        # ros2 topic pub /config_update std_msgs/msg/String "data: '{\"hello\":{\"there\":{\"test\":{\"dio\":false}}}}'" 
        
        # helper class to connect to the simulator
        self.peer = PeerUDP(SIMULATOR_ADDRESS)
    
    def config_test_handler(self, data: dict):
        print(data)

    def config_test_handler_2(self, data: dict):
        print(data)
    
    def config_test_handler_3(self, data: dict):
        raise ValueError("gigio")


    def _send_motion_packet(self, cmd: MotionCommand):
        axisid, value = cmd
        # packets structure: uint8 (packid) | uint8 (axisid) | float32 (value) 
        encoded = PACKID_MOTION + struct.pack("!Bf", axisid, value)
        self.peer.send(encoded)
    
    def _ping(self) -> bool:
        self.peer.send(PACKID_PING)
        packet = self.peer.recv(1)
        if packet == PACKID_PING:
            # if packet is not None and is a PING response, the simulator is ready
            return True
        return False

    def initialize_hw(self) -> bool:
        return self._ping()

    def deinitialize_hw(self) -> bool:
        return True
    
    def control(self, commands: list[MotionCommand]):
        # controls the simulated head hardware
        if len(commands) > 0:
            print(f"got {len(commands)} commands")
        for cmd in commands:
            # just forwards the packets to the simulator
            self._send_motion_packet(cmd)

# creating the actual controllers, all derived from the same class

"""
We dont actually need these, just load the base controller

class HeadCtrlSim(BaseControllerSim):
    def __init__(self):
        super().__init__("head-sim")
        self.subscribe_to_command_group([])

class BodyCtrlSim(BaseControllerSim):
    def __init__(self):
        super().__init__("body-sim")
        self.subscribe_to_command_group([])

class LeftArmCtrlSim(BaseControllerSim):
    def __init__(self):
        super().__init__("leftarm-sim")
        self.subscribe_to_command_group([])

class RightArmCtrlSim(BaseControllerSim):
    def __init__(self):
        super().__init__("rightarm-sim")
        self.subscribe_to_command_group([])

"""