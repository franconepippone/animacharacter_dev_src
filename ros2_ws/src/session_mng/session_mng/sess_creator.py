from typing import Callable, Any
from dataclasses import dataclass
import secrets
import pynng
from rclpy.logging import get_logger, RcutilsLogger

from pysafeudp import SafeUdpSock

import logging
from concurrent.futures import Future, CancelledError, TimeoutError

@dataclass
class SessionContext:
    nng_sock: pynng.Pair0
    nng_port: int
    stream_sock: SafeUdpSock
    stream_port: int
    stream_secret_key: str
    secret_token: str


@dataclass
class SessionCreationResult:
    success: bool
    context: SessionContext | None
    error_msg: str | None = None

# MAYBE THIS SHOULD NOT BE A NODE; just a regular class? external "master" node
# that host ros services and calls this class methods?

class SessionCreator:
    def __init__(self) -> None:
        self.logger = get_logger("session_creator")
        self.active_session: SessionContext | None = None

    def close_session(self) -> bool:
        ...

    def create_session(self) -> SessionCreationResult:
        """
        Opens sockets and returns session context.
        Returns None if a session could not be created.
        """

        if self.active_session is not None:
            return SessionCreationResult(
                success=False,
                context=None,
                error_msg="A session request was made during an already ongoing session, rejecting."
            )
        

        # XXX in here we should probably check if hardware is OK before starting a session
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

