from dataclasses import dataclass
import threading

from interfaces.msg import MotionframeArray

from pysafeudp.safeudpsock import SafeUdpSock

from session import SessionResourceManager, SessionRunner
from session.resource_manager import LoggerLike, LoggerLike, SessionDestructionError, SessionCreationError

import pynng
import secrets

# ====================
# SESSION CONTEXT
# ====================


@dataclass
class ACSessionContext:
    """
    Container class for a session's data: includes open sockets, ports, secret keys/tokens.
    This is a pure data container and does not implement session lifecycle logic.
    """
    nng_sock: pynng.Pair0
    nng_port: int
    stream_sock: SafeUdpSock
    stream_port: int
    stream_secret_key: str
    secret_token: str


# ====================
# SESSION RESOURCE MANAGER IMPLEMENTATION
# ====================

class ACSessResourceMng(SessionResourceManager[ACSessionContext]):
    """Create and destroy session transport resources."""

    def destroy(self, context: ACSessionContext):
        """Release all resources held by a session context."""
        try:
            context.nng_sock.close()
            context.stream_sock.close()
        except Exception as exc:
            raise SessionDestructionError() from exc

    def create(self) -> ACSessionContext:
        """Allocate transport resources and return a session context."""
        sess_sock = None
        stream_sock = None

        try:
            sess_token = secrets.token_urlsafe(64)

            sess_sock = pynng.Pair0(recv_timeout=5000, send_timeout=5000)
            sess_sock.listen("tcp://127.0.0.1:0")
            sess_addr = sess_sock.listeners[0].url
            sess_port = int(sess_addr.split(":")[-1])

            stream_secret_key = secrets.token_urlsafe(32)
            stream_sock = SafeUdpSock(stream_secret_key.encode())
            stream_port = stream_sock.bind()

            ctx = ACSessionContext(
                nng_sock=sess_sock,
                nng_port=sess_port,
                stream_sock=stream_sock,
                stream_port=stream_port,
                stream_secret_key=stream_secret_key,
                secret_token=sess_token,
            )
            self.logger.info(f"Session created successfully, ctx={ctx}")
            return ctx

        except Exception as exc:
            if sess_sock is not None:
                try:
                    sess_sock.close()
                except Exception:
                    pass
            if stream_sock is not None:
                try:
                    stream_sock.close()
                except Exception:
                    pass
            raise SessionCreationError() from exc


# ====================
# SESSION RUNNER IMPLEMENTATION
# ====================

from rclpy.publisher import Publisher

class ACSessionRunner(SessionRunner[ACSessionContext]):
    def __init__(self, motionframe_publisher: Publisher, config_publisher: Publisher, logger: LoggerLike | None = None) -> None:
        super().__init__(logger=logger)
        self.motionframe_publisher = motionframe_publisher
        self.config_publisher = config_publisher

    def run(self, ctx: ACSessionContext) -> None:
        """Core session logic, runs in a background thread. Should return when session ends."""
        # once this returns, session ends.

    ####
    #### --------------------------- SESSION IMPLEMENTATION ---------------------------
    ####

    def _motionframe_forwarder(self, ctx: ACSessionContext, stop_event: threading.Event):
        """Receive motionframes from the session socket and republish them."""
        while not stop_event.is_set():
            try:
                motionframes_raw = ctx.stream_sock.recv(timeout=1.0)
            except Exception as exc:
                self.logger.error(f"Error receiving motionframes: {exc}")
                continue
            
            # convert motionframes raw 

            motionframe_message = MotionframeArray()
            self.motionframe_publisher.publish(motionframe_message)

        stop_event.set()

    ## core method

    def _run_session(self, ctx: ACSessionContext):
        # once this returns, session ends.

        all_stop = threading.Event()
        
        t_stream = threading.Thread(
            target=self._motionframe_forwarder,
            args=(ctx, all_stop),
            daemon=True,
        )
        t_stream.start()
        t_stream.join()

    ###### --------------------------------------
