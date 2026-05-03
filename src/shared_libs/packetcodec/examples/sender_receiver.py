from __future__ import annotations
from packetcodec import BasePacket, PacketDecoder
from dataclasses import dataclass


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

# on the sender side
encoded = MyPacket.encode(1, 5, "my message")
print("encoded packet:", encoded)


# on the receiver side
decoder = PacketDecoder()
decoder.register_packet(MyPacket)

pkt = decoder.parse_bytes(encoded)
print("Parsed Packet", pkt, type(pkt))




# Using builtin PicklePacket to send arbitrary python data
from packetcodec import PicklePacket


encoded = PicklePacket.encode((1, 2, "hello", {"test":"dictionary"}, ["test", "list"]))

pkt = decoder.parse_bytes(encoded)
print("Parsed packet", pkt, type(pkt))