class PeerError(Exception):
    """Base class for all authmsg peer errors."""

class ConnectionError(PeerError):
    """Raised when a transport-level connection error occurs."""

class IsAlreadyInitialized(PeerError):
    """If an action requiring the peer to not be initialized is performed"""

class IsNotInitialized(PeerError):
    """An action requiring the peer to be initialized is performed"""

class ForbiddenOperation(PeerError):
    """Raised when an invalid operation is attempted"""

class AlreadyConnectedError(ConnectionError):
    """Raised when an operation is attempted on an already connected peer."""

