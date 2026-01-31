from dataclasses import dataclass
import secrets
import pynng
from rclpy.logging import get_logger

from pysafeudp import SafeUdpSock


@dataclass
class SessionContext:
    """
    Container class for a session's data: includes open sockets, ports, secret keys/tokens.
    This is only a (dataclass) container, does not implement any logic.
    """
    nng_sock: pynng.Pair0
    nng_port: int
    stream_sock: SafeUdpSock
    stream_port: int
    stream_secret_key: str
    secret_token: str


@dataclass
class SessionCreationResult:
    """
    Result of a session creation attempt. Contains success flag, session context if successful, and error message if any.
    """
    success: bool
    context: SessionContext | None
    error_msg: str | None = None


class SessionCreator:
    """
    This class implements the mechanics of creating and destroying session contexts. It is used by
    an external entity (e.g. SessManagerNode) to create or end sessions as needed.
    
    It exposes two symmetrical methods: 
    - create_session() -> SessionCreationResult 
    - destroy_session(context: SessionContext) -> bool

    This class is also stateless; it does not track active sessions internally.
    """

    def __init__(self) -> None:
        self.logger = get_logger("session_creator")

    def destroy_session(self, context: SessionContext) -> bool:
        """
        Attempts destruction of a session context.  
        Frees sockets and other resources.
        """
        try:
            context.nng_sock.close()
            context.stream_sock.close()
            self.logger.info("Session destroyed successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to destroy session: {e}")
            return False

    def create_session(self) -> SessionCreationResult:
        """
        Attempts construction of a new session context.

        Opens sockets and returns session context.
        Returns None if a session could not be created.
        """
    
        try:
            sess_token = secrets.token_urlsafe(64)

            sess_sock = pynng.Pair0(
                recv_timeout=5000, 
                send_timeout=5000
            )
            sess_sock.listen("tcp://127.0.0.1:0")   # binds on random port on this host
            sess_addr = sess_sock.listeners[0].url
            sess_port = int(sess_addr.split(":")[-1])

            stream_secret_key = secrets.token_urlsafe(32)
            stream_sock = SafeUdpSock(stream_secret_key.encode())
            stream_port: int = stream_sock.bind() # binds on random port on this host

            ctx = SessionContext(
                nng_sock=sess_sock,
                nng_port=sess_port,
                stream_sock=stream_sock,
                stream_port=stream_port,
                stream_secret_key=stream_secret_key,
                secret_token=sess_token
            )

            self.active_session = ctx
            return SessionCreationResult(
                success=True,
                context=ctx
            )

        except Exception as e:
            self.logger.error(f"An unexpected exception was raised inside 'create_session': {e}")
            return SessionCreationResult(
                success=False,
                context=None,
                error_msg="python generated an exception: " + str(e)
            )

