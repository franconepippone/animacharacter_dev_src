from __future__ import annotations

from typing import Any, Awaitable, Generic, Protocol, TypeVar, Callable
from dataclasses import dataclass, field
import time

from .proto_logger import LoggerLike, StupidLogger


SessCtxT = TypeVar("SessCtxT", contravariant=True)
SessCtxOutT = TypeVar("SessCtxOutT", covariant=True)


# ---------------------------------------------------------------------------
# Callback protocols
# ---------------------------------------------------------------------------

class SessionRunnerCallable(Protocol, Generic[SessCtxT]):
    async def __call__(self, ctx: SessCtxT, /) -> Any:
        ...


class SessionCleanupCallable(Protocol, Generic[SessCtxOutT]):
    async def __call__(self, handle: SessionHandle[SessCtxOutT], /) -> Any:
        ...


class SessionPrepareCallable(Protocol, Generic[SessCtxT]):
    async def __call__(self, ctx: SessCtxT, /) -> None:
        ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SessionRunnerError(RuntimeError):
    """Base exception for session runner errors."""


# ---------------------------------------------------------------------------
# Session handle
# ---------------------------------------------------------------------------

@dataclass
class SessionHandle(Generic[SessCtxT]):
    """External interface to an asynchronously running session."""

    ctx: SessCtxT

    creation_time: float = field(default_factory=time.time)

    result_value: Any = None
    crash_exception: BaseException | None = None

    _running: bool = False
    _stop_requested: bool = False
    _completed: bool = False

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time since the session handle was created."""
        return time.time() - self.creation_time

    def is_alive(self) -> bool:
        """Return whether the session is currently running."""
        return self._running and not self._completed

    def is_completed(self) -> bool:
        """Return whether the session has finished."""
        return self._completed

    def get_crash_exception(self) -> BaseException | None:
        """Return the exception that caused the session to crash, if any."""
        return self.crash_exception

    def result(self) -> Any:
        """Return the result value produced by the session."""
        return self.result_value

    def request_stop(self) -> None:
        """Request that the running session stops gracefully.

        This only sets the request flag. The session implementation must
        periodically check ``stop_requested`` and handle the request.
        """
        self._stop_requested = True

    @property
    def stop_requested(self) -> bool:
        """Return whether a stop has been requested."""
        return self._stop_requested


# ---------------------------------------------------------------------------
# Async session runner
# ---------------------------------------------------------------------------

class SessionRunnerAsync(Generic[SessCtxT]):
    """Manages asynchronous execution of a session context.

    No threads or asyncio primitives are used. The returned coroutine is
    intended to be scheduled/executed by the caller's async runtime, such as
    the ROS2 executor.
    """

    def __init__(
        self,
        runner: SessionRunnerCallable[SessCtxT] | None = None,
        cleanup: SessionCleanupCallable[SessCtxT] | None = None,
        prepare: SessionPrepareCallable[SessCtxT] | None = None,
        logger: LoggerLike | None = None,
    ) -> None:
        self.logger = logger if logger is not None else StupidLogger()

        if runner is not None:
            self.run = runner

        if prepare is not None:
            self.prepare = prepare

        self._cleanup_cbs: list[
            SessionCleanupCallable[SessCtxT]
        ] = [self.cleanup]

        if cleanup is not None:
            self._cleanup_cbs.append(cleanup)

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    def bind_session_runner(
        self,
        runner: SessionRunnerCallable[SessCtxT],
    ) -> None:
        """Bind an asynchronous session runner callback."""
        self.run = runner

    def bind_session_prepare(
        self,
        prepare: SessionPrepareCallable[SessCtxT],
    ) -> None:
        """Bind an asynchronous session preparation callback."""
        self.prepare = prepare

    def add_session_cleanup_cb(
        self,
        cleanup: SessionCleanupCallable[SessCtxT],
    ) -> None:
        """Add an asynchronous session cleanup callback."""
        self._cleanup_cbs.append(cleanup)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def start(self, ctx: SessCtxT) -> SessionHandle[SessCtxT]:
        """Execute a complete session asynchronously.

        The coroutine completes only after preparation, execution, and
        cleanup have all completed.

        The execution order is:

            1. prepare(ctx)
            2. run(ctx)
            3. cleanup callbacks

        Any exception raised by ``prepare`` or ``run`` is stored in the
        returned handle. Cleanup is always attempted.
        """
        handle = SessionHandle(ctx)
        handle._running = True

        self.logger.info("Session runner started.")

        try:
            await self.prepare(ctx)

            if handle.stop_requested:
                self.logger.info(
                    "Session stop requested before runner execution."
                )
            else:
                handle.result_value = await self.run(ctx)

        except BaseException as exc:
            handle.crash_exception = exc
            self.logger.error(
                f"Session runner crashed -> {exc}"
            )

        finally:
            self.logger.info(
                "Running session cleanup callbacks..."
            )

            for cleanup in self._cleanup_cbs:
                try:
                    await cleanup(handle)

                except Exception as exc:
                    self.logger.error(
                        f"Session cleanup raised an exception -> {exc}"
                    )

            handle._running = False
            handle._completed = True

        return handle

    # ------------------------------------------------------------------
    # Default callbacks
    # ------------------------------------------------------------------

    async def prepare(self, ctx: SessCtxT, /) -> None:
        """Default asynchronous preparation callback."""
        pass

    async def run(self, ctx: SessCtxT, /) -> Any:
        """Default asynchronous session runner."""
        raise NotImplementedError(
            "'run' method was not assigned or overridden, "
            "cannot run session."
        )

    async def cleanup(
        self,
        handle: SessionHandle[SessCtxT],
    ) -> None:
        """Default asynchronous cleanup callback."""
        pass