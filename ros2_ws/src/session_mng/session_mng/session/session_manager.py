from __future__ import annotations

from typing import Callable, Generic, TypeVar

import threading
from dataclasses import dataclass

from .resource_manager import SessionResourceManager
from .runner import SessionHandle, SessionRunner
from .proto_logger import LoggerLike, StupidLogger

SessCtxT = TypeVar("SessCtxT")


@dataclass
class SessionStartResult(Generic[SessCtxT]):
    success: bool
    handle: SessionHandle[SessCtxT] | None = None
    error_msg: str | None = None
    err_exception: Exception | None = None


class SessionManager(Generic[SessCtxT]):
    """
    Orchestrate a single session lifecycle. Configurable by passing custom SessionResourceManager and SessionRunner implementations to the constructor.
    Ensures only one session can be active at a time.
    An optional session creation criteria callable can be passed to the constructor, 
    to check for custom conditions before creating a session (e.g. check if a required hardware resource is available).
    """

    def __init__(
        self,
        sess_resource_manager: SessionResourceManager[SessCtxT],
        sess_runner: SessionRunner[SessCtxT],
        session_creation_criteria: Callable[[], bool] | None = None,
        logger: LoggerLike | None = None,
    ) -> None:
        self.logger = logger if logger is not None else StupidLogger()
        self._creator = sess_resource_manager
        self._runner = sess_runner

        def _combined_cleanup(ctx: SessCtxT) -> None:
            self._cleanup_active_session(ctx)
            self._runner.cleanup(ctx)

        self._runner.bind_session_cleanup(_combined_cleanup)
        self._session_creation_criteria = session_creation_criteria

        self.active_session: SessionHandle | None = None
        self._lock = threading.Lock()

    def new_session(self) -> SessionStartResult:
        """Create and start a new session if no active session is running."""
        with self._lock:
            # ensure only one session can be active at a time
            if self.active_session is not None:
                return SessionStartResult(
                    success=False,
                    error_msg="A session is already active.",
                )
            
            # validate if criteria for session are met
            if self._session_creation_criteria is not None and not self._session_creation_criteria():
                return SessionStartResult(
                    success=False,
                    error_msg="Session creation criteria not met.",
                )

            # OK, try to create session resources
            creation_result = self._creator.create_session()
            if not creation_result.success or creation_result.context is None:
                return SessionStartResult(
                    success=False,
                    error_msg=f"Session resource creation failed: {creation_result.exception_on_creation}",
                    err_exception=creation_result.exception_on_creation
                )
            
            # OK, try to start session runner
            try:
                handle = self._runner.start(creation_result.context)
                handle.join(0.5) # let it start and check if thread is alive, to catch immediate crashes
                if not handle.is_alive(): 
                    raise RuntimeError("Session runner thread unable to start.")
            except Exception as exc:
                self.logger.error(f"Failed to start session: {exc}")
                if creation_result.context is not None:
                    self._creator.destroy_session(creation_result.context)
                return SessionStartResult(
                    success=False,
                    error_msg=f"Session runner failed to start: {exc}",
                    err_exception=exc
                )

            # good, we are succesfully running a session
            self.active_session = handle

        self.logger.info("Session created and runner started.")
        return SessionStartResult(success=True, handle=handle)

    def terminate_session(self, timeout: float = 5.0) -> bool:
        """Request the active session to stop and wait for it to terminate.
        NOTE: this is only signaling system, the session runner must account for this."""
        with self._lock:
            if self.active_session is None:
                self.logger.warning("terminate_session called with no active session.")
                return False

            handle = self.active_session
            self.active_session = None

        handle.request_stop()
        handle.join(timeout)
        return not handle.is_alive()

    def _cleanup_active_session(self, ctx: SessCtxT) -> None:
        """Destroy session resources after the session runner has finished."""
        result = self._creator.destroy_session(ctx)
        if result.success:
            self.logger.info("Session cleanup completed.")
        else:
            self.logger.warning(
                f"""Session cleanup failed -> {result.exception_on_destruction}""",
            )

    def is_session_active(self) -> bool:
        """Return whether a session is currently active."""
        return self.active_session is not None

    def get_active_session(self) -> SessCtxT | None:
        """Return the context of the currently active session, if any."""
        return self.active_session.ctx if self.active_session is not None else None
