import socket
from typing import Optional, Tuple
from abc import ABC, abstractmethod

import pynng


from ..protocol.wire_protocol import SecureWireProtocol
from ..protocol.crypto import normalize_psk
from .exceptions import IsAlreadyInitialized, IsNotInitialized


Address = Tuple[str, int]

class PeerBase(ABC):
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
    def close(self):
        """Closes this peer forever. This ends the peer's lifecycle."""

    @abstractmethod
    def _drop_connection(self):
        """Drop the current connection (pipe). In contrast to 'close', this does not end this peer lifecycle,
        it should simply reset the peer in a waiting-for-connection state. 
        
        How connections are re-acquired is implementation dependant.
        """

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
        self._require_initialized()
        packet = self.proto.pack(msg)
        return self._transport_send(packet)

    def recv(self) -> bytes:
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
    def __init__(self, port: int, psk: str | bytes | None = None) -> None:
        super().__init__(psk or b'')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        self.sock.setblocking(True)
        self.peer_addr = None
        self._connected = False

    def dial(self, peer_addr: Address) -> None:
        self._require_not_initialized('Cannot dial after Peer is alrady initialized')
        self.peer_addr = peer_addr
        self._connect_besteffort()

    def is_initialized(self) -> bool:
        return self.peer_addr is not None

    def _connect_besteffort(self) -> bool:
        if self._connected:
            return True
        
        if not self.peer_addr:
            raise ForbiddenOperation('Cannot connect before dialing')
        try:
            self.sock.connect(self.peer_addr)
        except OSError:
            self._connected = False
            return False
        self._connected = True
        return True

    def _transport_send(self, packet: bytes) -> bool:
        if not self._connect_besteffort():
            return False
        
        if len(packet) < MIN_PACKET_SIZE:
            raise FramingError("Packet is too small")
        try:
            self.sock.send(packet)
            return True
        except OSError:
            self._connected = False
            return False

    def _transport_recv(self, timeout: float) -> bytes:
        if not self._connect_besteffort():
            return b""
        
        try:
            if timeout == 0:
                self.sock.setblocking(False)
            else:
                self.sock.setblocking(True)
                self.sock.settimeout(timeout)
            return self.sock.recv(65535)
        except OSError:
            self._connected = False
            return b""





class PeerTCP(PeerBase):
    def __init__(self, 
            psk: str | bytes | None = None,
            recv_timeout: float = 5.0,
            send_timeout: float = 5.0
        ) -> None:
        super().__init__(psk or b'')
        self.sock = pynng.Pair0(
            recv_timeout=int(recv_timeout*1000), 
            send_timeout=int(send_timeout*1000)
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

    def close(self):
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
 