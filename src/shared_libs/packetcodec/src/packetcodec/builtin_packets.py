from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import pickle

from .constants import *
from .utils import get_packtype_id


@dataclass
class BasePacket(ABC):
    """Abstract base Packet dataclass. Defines the base structure for any kind of packet.
    
    Fields:
    - `_raw_bytes` (bytes): Raw data extracted from the packet.

    Subclass this class to implement your own packet types (subclass can be decorated with `@dataclass`). 
    
    Subclasses must implement:
    ```
    @staticmethod
    def decode(src: bytes) -> YourPacketType:
        ...
        return YourPacketType(args...)

    @classmethod
    def encode(cls, your_args...) -> EncodedPNPPacket:
        ...
        return cls.finish_encode(your_bytes...)
    ```
    """
    _raw_bytes: bytes = field(repr=False, init=False)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        # encoder wrapper - adds additional packet data to the payload (mainly, packet id at the beginning)
        original_encode = cls.encode
        def encoder_wrapper(*args, **kwargs) -> bytes:
            payload = original_encode(*args, **kwargs)
            packid = get_packtype_id(cls)
            return packid.to_bytes(PACKTYPEID_SIZE_BYTES, "big") + payload

        # similar to applying a decorator
        cls.encode = encoder_wrapper

    @classmethod
    def get_typeid(cls) -> int:
        return get_packtype_id(cls)

    @property
    def size(self) -> int:
        return len(self._raw_bytes)
    
    # ----- user defined methods ----

    @staticmethod
    @abstractmethod
    def decode(bin: bytes) -> BasePacket: ...
    
    @staticmethod
    @abstractmethod
    def encode(*args, **kwargs) -> bytes: ...


@dataclass
class RawBytesPacket(BasePacket):
    """Packet for exchanging raw bytes data.
    
    [!] Note that using this is not recomended; creating a custom BasePacket subclass for you
    specific application should always be the first choice.
    """
    data: bytes # duplicate of raw_bytes, but visible through repr

    @staticmethod
    def decode(bin: bytes) -> RawBytesPacket:
        return RawBytesPacket(bin)

    @classmethod
    def encode(cls, bb: bytes) -> bytes:
        return bb

@dataclass
class UnknownPacket(BasePacket):
    """Packet of unknown / unregistered class.
    
    When no matching classes are found to decode a packet, 
    an UnknownPacket is received (stores raw data bytes in the `._raw_bytes` field)
    """
    typeid: int 

    @staticmethod
    def decode(bin: bytes) -> UnknownPacket:
        unknown_typeid = int.from_bytes(bin[:PACKTYPEID_SIZE_BYTES], "big")
        return UnknownPacket(unknown_typeid)
    
    @staticmethod
    def encode() -> bytes:
        raise RuntimeError("An unknown packet cannot be encoded.")

@dataclass
class TextPacket(BasePacket):
    """Packet for exchaning textual information (useful for logging).
    """
    text: str

    @staticmethod
    def decode(bin: bytes) -> TextPacket:
        return TextPacket(bin.decode())

    @staticmethod
    def encode(text:str) -> bytes:
        return text.encode()


@dataclass
class PicklePacket(BasePacket):
    """
    Contains any serializable python object using the pickle module.
    If unpickling fails, the 'valid' attribute is set to False.
    """

    obj: object
    valid: bool
    error: pickle.PickleError | None

    @staticmethod
    def decode(bin: bytes) -> PicklePacket:
        """Decodes bytes using the pickle.loads() function."""
        try:
            obj = pickle.loads(bin)
            return PicklePacket(obj, True, None)
        except pickle.PickleError as e:
            return PicklePacket(None, False, e)

    @staticmethod
    def encode(obj: object) -> bytes:
        """Encodes object using the pickle.dumps() function."""
        return pickle.dumps(obj)
