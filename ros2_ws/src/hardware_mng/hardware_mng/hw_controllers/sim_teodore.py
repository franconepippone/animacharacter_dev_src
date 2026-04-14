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
        self.s.bind(("0.0.0.0", 0))
        self.s.setblocking(False)

        self.host_addr = self.s.getsockname()
        self.peer_addr = peer_addr

    def send(self, packet: bytes) -> None:
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


SIMULATOR_ADDRESS = "127.0.0.1", 500

PACKID_MOTION = b'\x00'
PACKID_PING = b'\x01'

class BaseControllerSim(BaseHardwareController):
    """This controller is used to interface with a local/remote hardware simulator.
    This just encodes and forwards the motion commands as udp packets to the simulator.
    """
    
    def __init__(self, name: str):
        super().__init__(name, flush_freq=30.0)

        # helper class to drive the hardware
        self.peer = PeerUDP(SIMULATOR_ADDRESS)

    def _send_motion_packet(self, cmd: MotionCommand):
        axisid, value = cmd
        # packets are (bits): 8 (packid) | 8 (axisid) | 32 (value) 
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
    
    def control(self, commands: Iterable[MotionCommand]):
        # controls the simulated head hardware
        for cmd in commands:
            self._send_motion_packet(cmd)

# creating the actual controllers, all derived from the same class

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