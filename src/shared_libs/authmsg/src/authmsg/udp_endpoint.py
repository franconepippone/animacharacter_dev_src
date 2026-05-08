import asyncio
import select
import socket
from typing import Optional


class UDPEndpoint:
    RECV_BUFFSIZE = 65535

    def __init__(
        self,
        bind_port: int,
        bind_host: str = "0.0.0.0",
        timeout: float = 5.0,
    ):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host, bind_port))

        # ALWAYS non-blocking
        self.sock.setblocking(False)

        self._timeout = timeout
        self.peer_addr: Optional[tuple[str, int]] = None
    
    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, val: float):
        if val < 0.0: raise ValueError("Timeout cannot be negative")
        self._timeout = val

    @property
    def local_address(self) -> tuple[str, int]:
        """Returns local (ip, port) tuple."""
        return self.sock.getsockname()

    @property
    def local_port(self) -> int:
        """Returns local port to which socket is bound."""
        return self.sock.getsockname()[1]

    def close(self):
        self.sock.close()

    def connect(self, host: str, port: int):
        self.peer_addr = (host, port)
        self.sock.connect(self.peer_addr)

    def _require_peer(self) -> tuple[str, int]:
        if self.peer_addr is None:
            raise ValueError("Peer not configured")
        return self.peer_addr

    # SYNCHRONOUS API

    def send(self, data: bytes | bytearray) -> bool:
        self._require_peer()

        _, writable, _ = select.select([], [self.sock], [], self._timeout)

        if not writable:
            return False

        try:
            self.sock.send(data)
            return True
        except OSError:
            return False

    def recv(self) -> bytes | None:
        self._require_peer()

        readable, _, _ = select.select([self.sock], [], [], self._timeout)

        if not readable:
            return None

        try:
            return self.sock.recv(self.RECV_BUFFSIZE)
        except OSError:
            return None

    # ASYNC API

    async def asend(self, data: bytes | bytearray) -> bool:
        self._require_peer()

        loop = asyncio.get_running_loop()

        try:
            await asyncio.wait_for(
                loop.sock_sendall(self.sock, data),
                timeout=self._timeout,
            )
            return True

        except (asyncio.TimeoutError, OSError):
            return False

    async def arecv(self) -> bytes | None:
        self._require_peer()

        loop = asyncio.get_running_loop()

        try:
            return await asyncio.wait_for(
                loop.sock_recv(self.sock, self.RECV_BUFFSIZE),
                timeout=self._timeout,
            )

        except (asyncio.TimeoutError, OSError):
            return None