from .peer import PeerBase, Address
from .exceptions import IsNotInitialized, IsAlreadyInitialized
import pynng


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
        if self.sock.listeners:
            url: str = self.sock.listeners[0].url
            host, port = url.split('//')[1].split(':')
            return host, int(port)
        
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
 