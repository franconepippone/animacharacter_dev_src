from typing import Callable, Any
import pynng
from dataclasses import dataclass
import secrets
import logging

from rclpy.node import Node
from concurrent.futures import Future, CancelledError, TimeoutError

@dataclass
class SessionContext:
    sess_sock: pynng.Pair0
    sess_addr: str
    sess_id: str
    sess_authtoken: str

class SessionManagerNode(Node):
    MAX_SESSIONS: int = 1
    
    def __init__(self, max_sessions: int | None = None) -> None:
        if max_sessions: self.MAX_SESSIONS = max_sessions
        self.active_sessions: dict[str, SessionContext] = {}
        self.sess_ctx_future: Future[SessionContext] = Future()
    
    def wait_for_session(self, timeout: float | None = None) -> SessionContext | None:
        try:
            self.sess_ctx_future.result(timeout=timeout)
        except (CancelledError, TimeoutError):
            return None
        except Exception as e:
            self.get_logger().error("")

    def set_max_sessions(self, amount: int):
        assert amount > 1, "max session amount must be a nonzero, positive int"
        self.MAX_SESSIONS = amount

    def get_active_sessions(self) -> tuple[SessionContext, ...]:
        return tuple(self.active_sessions.values())

    def get_active_sessions_amount(self) -> int:
        return len(self.active_sessions)
    
    def close_session(self, sess_id: str) -> bool:
        if sess_id in self.active_sessions:

            ctx = self.active_sessions[sess_id]
            ctx.sess_sock.close()   # shuts session socket

            del self.active_sessions[sess_id]
            return True # session succesfully closed
        
        return False

    def create_session(self) -> SessionContext | None:
        """Creates a new session, opens socket and returns session context.
        Returns None if a session could not be created.
        """
        if self.get_active_sessions_amount() >= self.MAX_SESSIONS:
            return None

        sess_id = secrets.token_urlsafe(16)
        sess_authtoken = secrets.token_urlsafe(64)

        sess_sock = pynng.Pair0(
            recv_timeout=5000, 
            send_timeout=5000
        )
        sess_sock.listen("tcp://127.0.0.1:0")   # binds on random port
        sess_addr = sess_sock.listeners[0].url  # gets full url


        ctx = SessionContext(
            sess_sock,
            sess_addr,
            sess_id,
            sess_authtoken
        )

        self.active_sessions[sess_id] = ctx

        # store to queue, so 

        return ctx

