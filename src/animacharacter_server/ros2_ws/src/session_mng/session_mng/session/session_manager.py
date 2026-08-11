from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, TypeVar
import inspect
import threading
from dataclasses import dataclass

from rclpy.executors import Executor
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
    An optional session creation criteria async callable can be passed to the constructor, 
    to check for custom conditions before creating a session (e.g. check if a required hardware resource is available).
    """

    def __init__(
        self,
        sess_resource_manager: SessionResourceManager[SessCtxT],
        sess_runner: SessionRunner[SessCtxT],
        session_creation_criteria: Callable[[], bool | Awaitable[bool]] | None = None,
        cleanup_executor_provider: Callable[[], Executor | None] | None = None,
        logger: LoggerLike | None = None,
    ) -> None:
        self.logger = logger if logger is not None else StupidLogger()
        self._creator = sess_resource_manager
        self._runner = sess_runner
        self._cleanup_executor_provider = cleanup_executor_provider

        old_cleanup = self._runner.cleanup
        def _combined_cleanup(ctx: SessCtxT) -> None:
            try:
                result: Any = old_cleanup(ctx)
            except Exception as exc:
                self.logger.error(f"Session cleanup callback failed: {exc}")
                result = None

            if inspect.isawaitable(result):
                executor = self._cleanup_executor_provider() if self._cleanup_executor_provider is not None else None
                if executor is None:
                    self.logger.error("No executor available for async session cleanup. Cleanup will not run.")
                    self._cleanup_active_session(ctx)
                    return

                async def _async_cleanup_wrapper() -> None:
                    try:
                        await result
                    except Exception as exc:
                        self.logger.error(f"Async session cleanup failed: {exc}")
                    finally:
                        self._cleanup_active_session(ctx)

                executor.create_task(_async_cleanup_wrapper)
            else:
                self._cleanup_active_session(ctx)

        self._runner.bind_session_cleanup(_combined_cleanup)
        self._session_creation_criteria = session_creation_criteria

        self.active_session: SessionHandle | None = None
        self._lock = threading.Lock()

    async def new_session(self, args) -> SessionStartResult[SessCtxT]:
        """Create and start a new session if no active session is running. Must be awaited."""
        with self._lock:
            if self.active_session is not None:
                return SessionStartResult(
                    success=False,
                    error_msg="A session is already active.",
                )

        # validate if criteria for session are met
        if self._session_creation_criteria is not None:
            criteria_result = self._session_creation_criteria()
            if inspect.isawaitable(criteria_result):
                criteria_result = await criteria_result
            if not criteria_result:
                return SessionStartResult(
                    success=False,
                    error_msg="Session creation criteria not met.",
                )

        # OK, try to create session resources
        creation_result = self._creator.create_session(args)
        if not creation_result.success or creation_result.context is None:
            return SessionStartResult(
                success=False,
                error_msg=f"Session resource creation failed: {creation_result.exception_on_creation}",
                err_exception=creation_result.exception_on_creation
            )

        with self._lock:
            if self.active_session is not None:
                if creation_result.context is not None:
                    self._creator.destroy_session(creation_result.context)
                return SessionStartResult(
                    success=False,
                    error_msg="A session is already active.",
                )

            # OK, try to start session runner
            try:
                handle = self._runner.start(creation_result.context)
                handle.join(0.5)  # let it start and check if thread is alive, to catch immediate crashes
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
            self.active_session = None
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
