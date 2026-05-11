from typing import Tuple
from collections.abc import Sequence
import struct


packer = struct.Struct("Bf")

def encode_motionframe_packet(motionframe: Sequence[Tuple[int, float]]) -> bytearray:
    unit_size = packer.size
    buff = bytearray(len(motionframe) * unit_size)
    
    offset = 0
    for id, value in motionframe:
        packer.pack_into(buff, offset, id, value)
        offset += unit_size
    
    return buff

def decode_motionframe_packet(data: bytes | bytearray) -> list[tuple[int, float]]:
    unpack_from = packer.unpack_from
    unit_size = packer.size

    n = len(data) // unit_size
    out = [(-1, 0.0)] * n  # preallocate list

    offset = 0
    for i in range(n):
        out[i] = unpack_from(data, offset)
        offset += unit_size

    return out