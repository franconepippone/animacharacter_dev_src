from typing import Type, Dict, Tuple
import threading as tr
import hashlib

pack_id_table: Dict[str, int] = {}

def gen32bithash(input: str) -> int:
    md5_hash = hashlib.md5(input.encode()).hexdigest()
    hash_32_bit = int(md5_hash, 16) & 0xFFFFFFFF
    return hash_32_bit

def get_packtype_id(packet_type: Type) -> int:
    """Generates a unique 32bit hash of the packet class."""
    global pack_id_table

    input = packet_type.__name__
    if not input in pack_id_table:
        # look up table to speed up further accessing
        pack_id_table[input] = gen32bithash(input)
    
    return pack_id_table[input]
