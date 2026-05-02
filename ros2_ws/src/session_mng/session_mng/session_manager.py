from __future__ import annotations
from dataclasses import dataclass, field
import logging
import threading
import time

from .sess_creator import SessionCreationResult, SessionCreator, SessionContext
from .sess_runner import SessionRunner


@dataclass
class ActiveSession:
    context: SessionContext
    creation_time: float = field(default_factory=time.time)
    metadata: dict | None = None

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.creation_time

class SessionManager:
    """Manage a single session lifecycle.

    This class enforces the single-session rule and coordinates resource
    allocation, runner startup, and cleanup.
    """

    def __init__(self, creator: SessionCreator | None = None, runner: SessionRunner | None = None) -> None:
        self.logger = logging.getLogger("session_manager")
        self._creator = creator or SessionCreator()
        self._runner = runner or SessionRunner()
        self.active_session: ActiveSession | None = None
        self._lock = threading.Lock()

    def new_session(self) -> SessionCreationResult:
        """Create and start a new session if none is currently active."""
        with self._lock:
            if self.active_session is not None:
                return SessionCreationResult(
                    success=False,
                    context=None,
                    error_msg="A session is already active."
                )

            result = self._creator.create_session()
            if not result.success or result.context is None:
                return result # we fail early

            self.active_session = ActiveSession(context=result.context)
            try:
                self._runner.run(self.active_session.context)
            except Exception as exc:
                self.logger.error("Failed to start session runner: %s", exc)
                self._creator.destroy_session(self.active_session.context)
                self.active_session = None
                return SessionCreationResult(
                    success=False,
                    context=None,
                    error_msg=f"Session runner failed to start: {exc}"
                )

            self.logger.info("Session created and runner started.")
            return result

    def terminate_session(self) -> bool:
        """Stop the active session and release all resources."""
        with self._lock:
            if self.active_session is None:
                self.logger.warning("terminate_session called with no active session.")
                return False

            self._runner.stop()
            self._runner.join(timeout=5.0)
            success = self._creator.destroy_session(self.active_session.context)
            if success:
                self.logger.info("Session terminated successfully.")
            else:
                self.logger.warning("Session termination cleanup failed.")

            self.active_session = None
            return success

    def is_session_active(self) -> bool:
        """Return True if a session is currently active."""
        return self.active_session is not None

    def get_active_session(self) -> SessionContext | None:
        """Get the active session context, or None if there is no session."""
        return self.active_session.context if self.active_session is not None else None
