# Utility functions

def remap(x: float, to_max: int = 255):
    """Remaps x from range [0, 1] to range [0, to_max]"""
    return min(max(x, 0.0), 1.0) * to_max

def nrm(x: float) -> float:
    return (x+1.0)*0.5

def to_uint8(n: float | int) -> bytes:
    return int(n).to_bytes(1, "little", signed=False)

def to_int8(n: float | int):
    return int(n).to_bytes(1, "little", signed=True)

def to_int16(n: float | int):
    return int(n).to_bytes(2, "little", signed=True)

def to_uint16(n: float | int):
    return int(n).to_bytes(2, "little", signed=False)
