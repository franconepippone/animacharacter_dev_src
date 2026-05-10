from typing import Optional

from .peer import PeerBase, Address
from ..udp_endpoint import UDPEndpoint


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


