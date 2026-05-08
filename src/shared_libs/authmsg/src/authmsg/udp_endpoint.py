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

        self.timeout = timeout
        self.peer_addr: Optional[tuple[str, int]] = None

    @property
    def local_port(self) -> int:
        return self.sock.getsockname()[1]

    def close(self):
        self.sock.close()

    def connect(self, host: str, port: int):
        self.peer_addr = (host, port)
        self.sock.connect(self.peer_addr)

    # SYNCHRONOUS API

    def send(self, data: bytes | bytearray) -> bool:
        if self.peer_addr is None:
            raise ValueError("Peer not configured")

        _, writable, _ = select.select([], [self.sock], [], self.timeout)

        if not writable:
            return False

        try:
            self.sock.send(data)
            return True
        except OSError:
            return False

    def recv(self) -> bytes | None:
        readable, _, _ = select.select([self.sock], [], [], self.timeout)

        if not readable:
            return None

        try:
            return self.sock.recv(self.RECV_BUFFSIZE)
        except OSError:
            return None

    # ASYNC API

    async def asend(self, data: bytes | bytearray) -> bool:
        if self.peer_addr is None:
            raise ValueError("Peer not configured")

        loop = asyncio.get_running_loop()

        try:
            await asyncio.wait_for(
                loop.sock_sendall(self.sock, data),
                timeout=self.timeout,
            )
            return True

        except (asyncio.TimeoutError, OSError):
            return False

    async def arecv(self) -> bytes | None:
        loop = asyncio.get_running_loop()

        try:
            return await asyncio.wait_for(
                loop.sock_recv(self.sock, self.RECV_BUFFSIZE),
                timeout=self.timeout,
            )

        except (asyncio.TimeoutError, OSError):
            return None