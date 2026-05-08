import socket
from typing import Optional, Tuple
from abc import ABC, abstractmethod

import pynng
from ..udp_endpoint import UDPEndpoint

from ..protocol.wire_protocol import SecureWireProtocol
from ..protocol.crypto import normalize_psk
from .exceptions import IsAlreadyInitialized, IsNotInitialized


Address = Tuple[str, int]

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






class PeerUDP(PeerBase):
    """Datagram socket based Peer. Call 'dial' to set peer address. Supports asyncio.
    After 'close' is called, this object should not be reused.
    """
    def __init__(self, bind_port: int = 0, psk: Optional[str | bytes] = None, timeout: float = 5.0) -> None:
        super().__init__(psk or b'')
        self.udp = UDPEndpoint(bind_port)
        self.set_timeout(timeout)
        self._init = False

    @property
    def remote_address(self) -> Address: return self.udp._require_peer()
    @property
    def local_address(self) -> Address: return self.udp.local_address 

    def dial(self, host: str, port: int) -> None:
        """\"Connect\" the datagram socket to the specified address (UDP is connectionless,
        this does not perform any handshake)"""
        self._require_not_initialized('Cannot dial after Peer is alrady initialized')
        self.udp.connect(host, port)
        self._init = True
    
    def set_timeout(self, timeout: float):
        self.udp.timeout = timeout
    
    def _close(self):
        self.udp.close()
        self._init = False
    
    def _drop_connection(self):
        # this really does nothing?
        return

    def is_initialized(self) -> bool:
        return self._init

    def _transport_send(self, packet: bytes) -> bool:
        return self.udp.send(packet)

    def _transport_recv(self) -> bytes | None:
        return self.udp.recv()
    
    async def _transport_arecv(self) -> bytes | None:
        return await self.udp.arecv()
    
    async def _transport_asend(self, packet: bytes) -> bool:
        return await self.udp.asend(packet)





def _validate_timeout(timeout: float) -> int:
    """Converts timeout from secs in ms and raises if negative"""
    t = int(timeout*1000)
    if t < 0:
        raise ValueError("timeout cannot be negative")
    return t

class PeerTCP(PeerBase):
    """TCP Peer (based on pynng). Call 'dial' to connect to another peer, 'listen' to listen for connections.
    Supports asyncio. 
    """
    def __init__(self, 
            psk: str | bytes | None = None,
            recv_timeout: float = 5.0,
            send_timeout: float = 5.0
        ) -> None:
        super().__init__(psk or b'')
        self.sock = pynng.Pair0(
            recv_timeout=_validate_timeout(recv_timeout), 
            send_timeout=_validate_timeout(send_timeout)
        )
        self._init = False
        self.set_blocking(True, True)
    
    ### public API
    # two ways of initializing: listener or dialer

    def dial(self, host: str, port: int):
        self._require_not_initialized('Cannot dial after peer as already been initialized')
        self.sock.dial(f"tcp://{host}:{port}", block=False)
        self._init = True

    def listen(self, port: int, host: str = '0.0.0.0'):
        self._require_not_initialized('Cannot listen after peer as already been initialized')
        self.sock.listen(f"tcp://{host}:{port}")
        self._init = True
    
    def set_blocking(self, on_recv: bool = True, on_send: bool = True):
        """Set blocking mode for recv and send operations.   
        NOTE: Blocking is always enabled for async send / recv!"""
        self._block_on_recv = on_recv
        self._block_on_send = on_send
    
    def set_timeout(self, recv: float | None = None, send: float | None = None):
        """Sets timeouts for send and recv operations (only works if in blocking mode)"""
        if send is not None: self.sock.send_timeout = _validate_timeout(send)
        if recv is not None: self.sock.recv_timeout = _validate_timeout(recv)

    @property
    def remote_address(self) -> Address:
        if not self.sock.pipes:
            raise IsNotInitialized("Failed to get address (socket has no pipes)")
        pipe: pynng.nng.Pipe = self.sock.pipes[0]
        return pipe.remote_address
    
    @property
    def local_address(self) -> Address:
        if not self.sock.pipes:
            raise IsNotInitialized("Failed to get address (socket has no pipes)")
        pipe: pynng.nng.Pipe = self.sock.pipes[0]
        return pipe.local_address

    # abstract methods implementation

    def _drop_connection(self):
        # closes all pipes (for pair0 there should ever only be 1)
        for pipe in self.sock.pipes:
            pipe: pynng.nng.Pipe
            pipe.close()

    def is_initialized(self) -> bool:
        return self._init

    def _close(self):
        self.sock.close()

    # send / recv

    def _transport_send(self, packet: bytes) -> bool:
        try:
            self.sock.send(packet, self._block_on_send)
            return True
        except (pynng.exceptions.Timeout, pynng.exceptions.TryAgain):
            return False

    def _transport_recv(self) -> bytes | None:
        try:
            return self.sock.recv(self._block_on_recv)
        except (pynng.exceptions.Timeout, pynng.exceptions.TryAgain):
            return None

    # async send / recv

    async def _transport_asend(self, packet: bytes) -> bool:
        try:
            await self.sock.asend(packet)
            return True
        except (pynng.exceptions.Timeout, pynng.exceptions.TryAgain):
            return False

    async def _transport_arecv(self) -> bytes | None:
        try:
            return await self.sock.arecv()
        except (pynng.exceptions.Timeout, pynng.exceptions.TryAgain):
            return None
 