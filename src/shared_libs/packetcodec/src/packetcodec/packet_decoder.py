from __future__ import annotations
from typing import Dict, Type

from .utils import  get_packtype_id
from .builtin_packets import *
from .constants import *


class PacketDecoder:
    """
    The packet decoder in the packetcodec library. This will try to decode
    any sequence of bytes passed to the `parse_bytes` method into an object of
    one of the registered packet classes (derived from `BasePacket`). 
    To register a new packet class, call `register_packet(YourPacketClass)`.

    If a packet cannot be parsed by `parse_bytes`, an `UnknownPacket` will be returned.

    Example usage (Python 3.10+):
    ```python
    # initialization
    decoder = PacketDecoder()
    decoder.register_packet(MyPacket)
    ...

    # execution
    data = #... received some binary data from sockets / serial / other sources ...
    packet = decoder.parse_bytes(data)
    match packet:
        case UnknownPacket():
            # received a packet of unknown class
        case MyPacket():
            # we just received a packet of class MyPacket
            print(packet.mydata1, packet.mydata2) # we can access the attributes

    ```
    """
    def __init__(self):
        # creates its own copy of the default packet_table
        self._PACKET_TABLE: Dict[int, Type[BasePacket]] = {}
        self.register_packet(TextPacket)
        self.register_packet(RawBytesPacket)
        self.register_packet(PicklePacket)
        #self.register_packet(UnknownPacket) we should never receive this directly

    # ---------------- interface ----------------
         
    def register_packet(self, packet_class: Type[BasePacket]):
        """Registers a new packet type. From now on, packets of the new type will can be
        automatically decoded.
        """
        packet_typeid: int = get_packtype_id(packet_class) #32 bit
        # add new entry to table
        self._PACKET_TABLE[packet_typeid] = packet_class
    
    def parse_bytes(self, data: bytes | memoryview | bytearray) -> BasePacket:
        """Attempts to decode a packet from bytes
        """
        pack_typeid = int.from_bytes(data[:PACKTYPEID_SIZE_BYTES], "big")   # first 32 bit are pack typeid
        packet_class = self._PACKET_TABLE.get(pack_typeid, UnknownPacket)
        
        payload_data: bytes = data[PACKTYPEID_SIZE_BYTES:]
        packet = packet_class.decode(payload_data)
        packet._raw_bytes = payload_data
        return packet 