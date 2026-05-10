from typing import Tuple
from abc import ABC, abstractmethod

from ..protocol.wire_protocol import SecureWireProtocol
from ..protocol.crypto import normalize_psk
from .exceptions import IsAlreadyInitialized, IsNotInitialized


type Address = Tuple[str, int]

class PeerBase(ABC):
    """Base class for a Peer in a peer-to-peer authenticated connection.
    Integrity and authentication are provided via psk-HMAC, and replay protection is provided via seq. number.

    Use 'send' / 'recv' to exchange data with peer. Derived classes implement '_transport_send' and
    '_transport_recv' to provide transport-dependant logic for forwarding / receiving bytes. Derived classes
    should also implement some kind of 'dial' or 'connect' method to enstablish the connection, and setting the
    peer state to initialized (overriding 'is_initialized').

    Optional async '_transport_asend' and '_transport_arecv' can be implemented for async support via
    'asend' / 'arecv'.

    """
    def __init__(self, psk: str | bytes) -> None:
        self.proto = SecureWireProtocol(normalize_psk(psk))
    
    def set_psk(self, psk: str | bytes):
        self.proto.set_psk(normalize_psk(psk))

    @property
    def remote_address(self) -> Address: raise NotImplementedError()
    @property
    def local_address(self) -> Address: raise NotImplementedError()

    @abstractmethod
    def is_initialized(self) -> bool:
        """Returns True if the peer is ready to send or recv"""

    @abstractmethod
    def _close(self): ...

    @abstractmethod
    def _drop_connection(self):
        """Drop the current connection (pipe). In contrast to 'close', this does not end this peer lifecycle,
        it should simply reset the peer in a waiting-for-connection state. 
        
        How connections are re-acquired is implementation dependant.
        """

    def close(self):
        """Closes this peer forever. This ends the peer's lifecycle."""
        self._require_initialized()
        self._close()

    def _require_initialized(self):
        if not self.is_initialized():
            raise IsNotInitialized('Peer must be initialized')

    def _require_not_initialized(self, errmsg: str = 'Operation invalid after Peer is initialized'):
        if self.is_initialized():
            raise IsAlreadyInitialized(errmsg)
    
    def _finish_recv(self, packet: bytes | None) -> bytes:
        # last phase of recv and arecv
        if packet is None:
            return b""
        msg = self.proto.unpack(packet)
        if msg is None:
            # there was an error during unpacking, msg is wrong / unauthorized, let's drop the connection
            self._drop_connection()
            return b""
        return msg

    def send(self, msg: bytes) -> bool:
        """Sends a msg to peer. Returns 'True' on success."""
        self._require_initialized()
        packet = self.proto.pack(msg)
        return self._transport_send(packet)

    def recv(self) -> bytes:
        """Attempts reception of a msg from peer. This might block or timeout,
        depending on the derived class implementation. Usually and empty byte object b'' 
        is returned when nothing is received.
        """
        self._require_initialized()
        packet = self._transport_recv()
        return self._finish_recv(packet)
    
    @abstractmethod
    def _transport_send(self, packet: bytes) -> bool: ...
    @abstractmethod
    def _transport_recv(self) -> bytes | None: ...

    # Aysnc counterpart

    async def asend(self, msg: bytes) -> bool:
        self._require_initialized()
        packet = self.proto.pack(msg)
        return await self._transport_asend(packet)

    async def arecv(self) -> bytes:
        self._require_initialized()
        packet = await self._transport_arecv()
        return self._finish_recv(packet)

    # optional to override these
    async def _transport_asend(self, packet: bytes) -> bool: raise NotImplementedError()
    async def _transport_arecv(self) -> bytes | None: raise NotImplementedError()
