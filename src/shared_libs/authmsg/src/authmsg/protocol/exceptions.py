
class ProtocolException(Exception):
    """Any exception concerning protocol"""

class AuthenticationError(ProtocolException):
    """Raised when HMAC authentication fails."""

class SequenceError(ProtocolException):
    """Raised when a message sequence number is invalid / replayed."""

class FramingError(ProtocolException):
    """Raised when a framed TCP packet is malformed."""