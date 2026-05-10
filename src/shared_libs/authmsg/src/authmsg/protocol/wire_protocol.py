
from .protocol import encode_packet, decode_packet
from .exceptions import FramingError, SequenceError, AuthenticationError

class SecureWireProtocol:
    """
    Middle layer for an authenticated messaging session (no encryption!).   
    Use 'pack(msg)' to get a ready-to-send frame, call 'unpack' to get back and validate the msg.

    Can be used on top of any transport type to provide integrity, authentication (via psk)
    and replay protection (via seq. number)
    """
    def __init__(self, psk: bytes) -> None:
        self.psk = psk
        self.send_sequence: int = 0
        self.last_received_sequence: int = 0
    
    def set_psk(self, psk: bytes):
        self.psk = psk
    
    def pack(self, msg: bytes) -> bytes:
        """Construct a ready-to-send frame wrapping 'msg'"""
        self.send_sequence += 1
        return encode_packet(self.send_sequence, msg, self.psk)
        
    def unpack_raise(self, data: bytes) -> bytes:
        """Same as unpack, but raises if validation fails."""
        seq, msg = decode_packet(data, self.psk, self.last_received_sequence)
        self.last_received_sequence = seq
        return msg
    
    def unpack(self, data: bytes) -> bytes | None:
        """Attempts to unpack a received frame. Returns None if validation fails 
        (format invalid, hmac wrong or seq number wrong)"""
        try:
            return self.unpack_raise(data)
        except (FramingError, AuthenticationError, SequenceError):
            return None