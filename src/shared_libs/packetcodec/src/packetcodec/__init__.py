"""
A simple Python system to manage encoding / decoding of Python Objects to / from a byte sequence.
Useful for exchanging structured messages over a binary communication channel (e.g sockets, serial, etc..)

A Packet is an object of class derived from `BasePacket`. It must implement an `encode()` and `decode()` methods.
To get an encoded packet byte sequence, directly call the method `encode()`.
To get a packet object from a (possibly received) byte sequence, a `PacketDecoder` is needed.
See the docstric for `PacketDecoder` for more in-depth explanation.
"""

from .builtin_packets import (
    BasePacket,
    UnknownPacket,
    PicklePacket,
    RawBytesPacket
) 
from .packet_decoder import PacketDecoder