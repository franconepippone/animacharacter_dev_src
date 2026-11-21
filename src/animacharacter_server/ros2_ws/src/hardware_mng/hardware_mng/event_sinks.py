from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Generic, TypeVar, cast

from rclpy.executors import Executor
from rclpy.logging import RcutilsLogger
from rclpy.task import Future

from lifecycle_pkg.events import EventSink, LifecycleEvent, LogLevel

T = TypeVar("T")


class ExecutorEventQueue(Generic[T]):
    """Thread-safe event queue awaitable by a ROS executor task."""

    def __init__(self) -> None:
        self._events: deque[T] = deque()
        self._lock = Lock()
        self._executor: Executor | None = None
        self._waiter: Future[T] | None = None

    def attach_executor(self, executor: Executor) -> None:
        """Associate pending reads with the node's executor."""
        with self._lock:
            if self._executor is not None and self._executor is not executor:
                raise RuntimeError("Event queue is already bound to another executor")
            self._executor = executor

    def put(self, event: T) -> None:
        """Queue an event and wake a pending executor coroutine, if present."""
        with self._lock:
            waiter = self._waiter
            if waiter is None or waiter.done():
                self._waiter = None
                self._events.append(event)
                return
            self._waiter = None

        waiter.set_result(event)

    async def get(self) -> T:
        """Await the next event without blocking the ROS executor."""
        with self._lock:
            if self._events:
                return self._events.popleft()
            if self._executor is None:
                raise RuntimeError("Event queue must be attached to an executor")
            if self._waiter is not None and not self._waiter.done():
                raise RuntimeError("Event queue supports one pending consumer")
            waiter: Future[T] = Future(executor=self._executor)
            self._waiter = waiter

        return cast(T, await waiter)


class RcutilsEventSink(EventSink):
    """Log lifecycle events through an rclpy logger."""

    def __init__(self, logger: RcutilsLogger, controller_name: str) -> None:
        self._logger = logger
        self._controller_name = controller_name

    def emit(self, event: LifecycleEvent) -> None:
        message = event.message or type(event).__name__
        log_message = f"[{self._controller_name}] {message}"
        if event.level == LogLevel.DEBUG:
            self._logger.debug(log_message)
        elif event.level == LogLevel.WARNING:
            self._logger.warning(log_message)
        elif event.level == LogLevel.ERROR:
            self._logger.error(log_message)
        else:
            self._logger.info(log_message)


class ControllerEventSink(EventSink):
    """Pass controller lifecycle events to the manager without ROS calls."""

    def __init__(
        self,
        controller_name: str,
        event_queue: ExecutorEventQueue[tuple[str, LifecycleEvent]],
    ) -> None:
        self._controller_name = controller_name
        self._event_queue = event_queue

    def emit(self, event: LifecycleEvent) -> None:
        self._event_queue.put((self._controller_name, event))
