from __future__ import annotations

from queue import SimpleQueue

from rclpy.logging import RcutilsLogger

from lifecycle_pkg.events import EventSink, LifecycleEvent, LogLevel


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
        event_queue: SimpleQueue[tuple[str, LifecycleEvent]],
    ) -> None:
        self._controller_name = controller_name
        self._event_queue = event_queue

    def emit(self, event: LifecycleEvent) -> None:
        self._event_queue.put((self._controller_name, event))
