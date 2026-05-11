from typing import Tuple
from collections.abc import Sequence
import struct
from array import array

# ===========================================================
#                     MOTIONFRAME PACKET
# ===========================================================
# 
# Each Motionframe packet is a contiguous sequence of records.
# Every record has a fixed binary layout:
# 
#     +---------+---------------------------+
#     | 2 bytes |        4 bytes            |
#     +---------+---------------------------+
#     |   ID    |        VALUE (float32)    |
#     +---------+---------------------------+
# 
# Record size: 6 bytes
# 
# Packet layout (N records):
# 
#     +---------+---------+---------+---------+-----+
#     | Rec 0   | Rec 1   | Rec 2   | Rec 3   | ... |
#     +---------+---------+---------+---------+-----+
#       0..5      6..11     12..17    18..23   ...
# 
# Where each record is:
# 
#     Offset +0 : uint16  → actuator ID
#     Offset +2 : float32 → actuator value
# 
# Example (N = 3):
# 
#     Byte index:
#         0   1   2   3   4   5   6   7   8   9  10  11  ...
#         |---ID0---|----VALUE0----|---ID1---|----VALUE1----| ...
# 
# ===========================================================


packer = struct.Struct("Hf")


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

def decode_motionframe_packet_into_arrays(data: bytes | bytearray):
    # faster ros2 native implementation
    unpack_from = packer.unpack_from
    unit_size = packer.size

    n = len(data) // unit_size
    ids = array('H', (0,)) * n      # preallocate
    vals = array('f', (0.0,)) * n   # preallocate

    offset = 0
    for i in range(n):
        id_val, float_val = unpack_from(data, offset)
        ids[i] = id_val
        vals[i] = float_val
        offset += unit_size

    return ids, vals