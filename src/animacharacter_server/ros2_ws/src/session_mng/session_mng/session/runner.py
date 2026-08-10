from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

import threading
from dataclasses import dataclass, field
import time

from .proto_logger import LoggerLike, StupidLogger

SessCtxT = TypeVar("SessCtxT", contravariant=True)

# makes sure runner and cleanup supports both run via callback assigment or via inheritance ovveride
class SessionRunnerCallable(Protocol, Generic[SessCtxT]):
    def __call__(self, ctx: SessCtxT) -> Any: ...

class SessionCleanupCallable(Protocol, Generic[SessCtxT]):
    def __call__(self, ctx: SessCtxT) -> Any: ...

# exception
class SessionRunnerError(RuntimeError): ...


@dataclass
class SessionHandle(Generic[SessCtxT]):
    """External interface object to a running session, returned by SessionRunner.start()."""
    ctx: SessCtxT
    _stop_request: threading.Event
    thread: threading.Thread | None = None
    creation_time: float = field(default_factory=time.time)
    result_value: Any = None
    crash_exception: BaseException | None = None

    @property
    def elapsed_time(self) -> float:
        """Return the elapsed time since the session handle was created."""
        return time.time() - self.creation_time

    def join(self, timeout: float | None = None) -> None:
        """Wait for the session thread to finish (or timeout times out)."""
        if self.thread is not None:
            self.thread.join(timeout)

    def is_alive(self) -> bool:
        """Return whether the session thread is still alive."""
        return self.thread.is_alive() if self.thread is not None else False

    def get_crash_exception(self) -> BaseException | None:
        """Return the exception that caused a session crash, if any."""
        return self.crash_exception

    def result(self) -> Any:
        """Return the result value from the session run method."""
        return self.result_value

    def request_stop(self) -> None:
        """Request that a running session stops gracefully."""
        self._stop_request.set()


class SessionRunner(Generic[SessCtxT]):
    """Manages execution of a session context in a background thread."""

    def __init__(
        self,
        runner: SessionRunnerCallable[SessCtxT] | None = None,
        cleanup: SessionCleanupCallable[SessCtxT] | None = None,
        logger: LoggerLike | None = None,
    ) -> None:
        self.logger = logger if logger is not None else StupidLogger()
        if runner is not None:
            self.run = runner
        if cleanup is not None:
            self.cleanup = cleanup

    def bind_session_runner(self, runner: SessionRunnerCallable[SessCtxT]) -> None:
        """Bind a session run callback."""
        self.run = runner

    def bind_session_cleanup(self, cleanup: SessionCleanupCallable[SessCtxT]) -> None:
        """Bind a session cleanup callback."""
        self.cleanup = cleanup

    def start(self, ctx: SessCtxT) -> SessionHandle[SessCtxT]:
        """Start a background thread to execute the session, returns a handle to the active session"""
        stop_event = threading.Event()
        handle = SessionHandle(ctx, stop_event)
        handle.thread = threading.Thread(
            target=self._run_session_wrapper,
            args=(ctx, handle),
            daemon=True,
            name=f"session_runner_{id(handle)}",
        )
        handle.thread.start()
        return handle

    def _run_session_wrapper(self, ctx: SessCtxT, handle: SessionHandle[SessCtxT]) -> None:
        """Run the session and ensure cleanup executes even if the session crashes."""
        self.logger.info("Session runner started.")
        try:
            handle.result_value = self.run(ctx)
        except BaseException as exc:
            handle.crash_exception = exc
            self.logger.error(f"Session runner crashed: {exc}")
        finally:
            self.logger.info("Session runner stopping")
            try:
                self.cleanup(ctx)
            except Exception as exc:
                self.logger.error(f"Session cleanup raised an exception: {exc}")

    def run(self, ctx: SessCtxT) -> Any:
        """Default runner function, should be overridden by user or set via constructor."""
        raise NotImplementedError("'run' method was not assigned or overridden, cannot run session.")

    def cleanup(self, ctx: SessCtxT) -> None:
        """Default cleanup function, can be overridden by user or set via constructor."""
        pass
