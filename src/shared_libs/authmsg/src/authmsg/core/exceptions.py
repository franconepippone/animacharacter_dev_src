class PeerError(Exception):
    """Base class for all authmsg peer errors."""

class IsAlreadyInitialized(PeerError):
    """If an action requiring the peer to not be initialized is performed"""

class IsNotInitialized(PeerError):
    """An action requiring the peer to be initialized is performed"""