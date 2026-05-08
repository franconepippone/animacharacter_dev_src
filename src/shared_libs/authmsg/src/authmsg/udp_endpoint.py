import socket
import asyncio

class UDPEndpoint:
    RECV_BUFFSIZE = 65535

    def __init__(self, bind_port: int, bind_host: str = '0.0.0.0', timeout: float = 5.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host, bind_port))
        self.peer_addr: socket._Address | None = None
        self._connected = False
        self.set_timeout(timeout)
    
    def set_timeout(self, timeout: float):
        """Set timeout for send/recv operations. A timeout of 0 sets socket in non-blocking mode.
        """
        if timeout < 0: raise ValueError("timeout must be positive")
        self._timeout = timeout
        if timeout == 0:
            self.sock.setblocking(False)
        else:
            self.sock.setblocking(True)
            self.sock.settimeout(timeout)

    def connect(self, host: str, port: int):
        self.peer_addr = (host, port)
        self._try_connect()
    
    async def arecv(self) -> bytes | None:
        if self._try_connect():
            loop = asyncio.get_running_loop()
            try:
                return await asyncio.wait_for(loop.sock_recv(self.sock, self.RECV_BUFFSIZE), self._timeout)
            except asyncio.TimeoutError:
                return None
            except OSError:
                self._mark_disconnected()

        return None

    async def asend(self, data: bytes | bytearray) -> bool:
        if self._try_connect():
            loop = asyncio.get_running_loop()
            try:
                await asyncio.wait_for(loop.sock_sendall(self.sock, data), self._timeout)
            except asyncio.TimeoutError:
                return False
            except OSError:
                self._mark_disconnected()

        return self._connected

    def send(self, data: bytes | bytearray) -> bool:
        if self._try_connect():
            try:
                self.sock.send(data)
            except (TimeoutError, BlockingIOError):
                # we return false cuz we did not succed, but we dont disconnect
                return False
            except OSError:
                self._mark_disconnected()
        
        return self._connected
    
    def recv(self) -> bytes | None:
        if self._try_connect():
            try:
                return self.sock.recv(self.RECV_BUFFSIZE)
            except (TimeoutError, BlockingIOError):
                return None
            except OSError:
                self._mark_disconnected()
        return None        

    def _mark_disconnected(self):
        self._connected = False

    def _try_connect(self) -> bool:
        """If not connected, attempts connection"""
        if self._connected: return True
        if self.peer_addr is None:
            raise ValueError('Peer address is not set, cannot connect')
        
        try:
            self.sock.settimeout(0.0) # make sure this is non-blocking
            self.sock.connect(self.peer_addr)
            self._connected = True
        except OSError:
            self._connected = False
        
        self.sock.settimeout(self._timeout)
        return self._connected