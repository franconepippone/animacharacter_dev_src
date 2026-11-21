from __future__ import annotations

import logging

from lifecycle_pkg.events import (
    FanOutEventSink,
    LogEvent,
    LogLevel,
    StdlibLoggingSink,
)


class RecordHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_stdlib_logging_sink_forwards_level_message_and_event() -> None:
    logger = logging.Logger("test.lifecycle_pkg.events", level=logging.WARNING)
    handler = RecordHandler()
    logger.addHandler(handler)
    event = LogEvent(level=LogLevel.WARNING, message="hardware warning")
    sink = StdlibLoggingSink(logger)

    sink.emit(event)

    assert len(handler.records) == 1
    assert handler.records[0].levelno == logging.WARNING
    assert handler.records[0].getMessage() == "hardware warning"
    assert handler.records[0].lifecycle_event is event


def test_fan_out_event_sink_forwards_to_all_sinks_after_failure() -> None:
    received: list[LogEvent] = []

    class RecordingSink:
        def emit(self, event: LogEvent) -> None:
            received.append(event)

    class FailingSink:
        def emit(self, event: LogEvent) -> None:
            raise RuntimeError("sink unavailable")

    event = LogEvent(message="fan out")
    sink = FanOutEventSink(
        [RecordingSink(), FailingSink(), RecordingSink()]
    )

    sink.emit(event)

    assert received == [event, event]
