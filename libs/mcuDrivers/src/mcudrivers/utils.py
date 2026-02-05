# Utility functions

def tobyte(x: int) -> int:
    """clamps integer to byte range"""
    return min(max(x, 0), 255)

def remap(x: float, to_max: int = 255):
    """Remaps x from range [0, 1] to range [0, to_max]"""
    return min(max(x, 0.0), 1.0) * to_max

def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x

def topwm8(x: float) -> int:
    """Maps float in range [0, 1] to integer in [0, 255]"""
    return min(max(int(x) * 255, 0), 1)

def topwm12(x: float) -> int:
    """Maps float in range [0, 1] to integer in [0, 4095]"""
    return min(max(int(x) * 4095, 0), 1)

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
