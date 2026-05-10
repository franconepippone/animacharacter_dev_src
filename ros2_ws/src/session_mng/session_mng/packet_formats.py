from __future__ import annotations
from dataclasses import dataclass
from packetcodec import BasePacket


@dataclass
class HeartBeat(BasePacket):
    """Implements an echo mechanism. Regularly sent from client to notify the server of its presence.
    Server disconnects client if heartbeat is not received within timeout
    """
    nonce: bytes

    @staticmethod
    def encode(nonce: bytes): return nonce
    @staticmethod
    def decode(bin: bytes): return HeartBeat(nonce=bin)


# define your own packet scheme
@dataclass
class MyPacket(BasePacket):
    val1: int
    val2: float
    msg: str

    # optionally, encode could be called on the instance itself, but it's preferred to implement static encode in order to avoid an object instantiation
    #def selfencode(self) -> bytes:
    #    return self.encode(self.val1, self.val2, self.msg)

    @staticmethod
    def encode(val1: int, val2: float, msg: str) -> bytes:
        return "-".join([str(val1), str(val2), msg]).encode()
    
    @staticmethod
    def decode(bin: bytes) -> MyPacket:
        val1_str, val2_str, msg = bin.decode().split("-")
        return MyPacket(int(val1_str), int(val2_str), msg)
 
