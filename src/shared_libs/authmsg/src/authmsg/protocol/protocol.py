from typing import Tuple

from .crypto import validate_signature, make_signature
from .exceptions import AuthenticationError, FramingError, SequenceError


SEQUENCE_SIZE = 8
HMAC_SIZE = 32
MIN_PACKET_SIZE = SEQUENCE_SIZE + HMAC_SIZE
MAX_UDP_PAYLOAD = 65507

def encode_packet(sequence: int, payload: bytes, psk: bytes) -> bytes:
    payload = payload or b""
    signature = make_signature(psk, sequence, payload)
    return sequence.to_bytes(SEQUENCE_SIZE, "big") + payload + signature


def decode_packet(data: bytes, psk: bytes, last_sequence: int | None = None) -> Tuple[int, bytes]:
    if len(data) < MIN_PACKET_SIZE:
        raise FramingError("Packet is too short to contain a valid header and signature")

    sequence = int.from_bytes(data[:SEQUENCE_SIZE], "big")
    tag = data[-HMAC_SIZE:]
    payload = data[SEQUENCE_SIZE:-HMAC_SIZE]

    if not validate_signature(psk, sequence, payload, tag):
        raise AuthenticationError("HMAC validation failed")

    if last_sequence is not None and sequence <= last_sequence:
        raise SequenceError("Packet sequence number is not strictly increasing")

    return sequence, payload

def ensure_valid_packet_size(payload: bytes) -> None:
    if len(payload) > MAX_UDP_PAYLOAD - MIN_PACKET_SIZE:
        raise ValueError("Payload is too large for UDP transport")