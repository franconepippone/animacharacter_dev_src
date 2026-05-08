import hashlib
import hmac


def normalize_psk(psk: str | bytes) -> bytes:
    if isinstance(psk, str):
        return psk.encode("utf-8")
    if isinstance(psk, bytes):
        return psk
    raise TypeError("PSK must be bytes or str")


def make_signature(psk: bytes, sequence: int, payload: bytes) -> bytes:
    sequence_bytes = sequence.to_bytes(8, "big")
    data = sequence_bytes + payload
    return hmac.new(psk, data, hashlib.sha256).digest()


def validate_signature(psk: bytes, sequence: int, payload: bytes, tag: bytes) -> bool:
    expected = make_signature(psk, sequence, payload)
    return hmac.compare_digest(expected, tag)
