from __future__ import annotations

import logging

from lifecycle_pkg import (
    FanOutEventSink,
    LogEvent,
    LogLevel,
    StdlibLoggingSink,
)


def test_stdlib_logging_sink_forwards_level_message_and_event(caplog) -> None:
    logger = logging.getLogger("test.lifecycle_pkg.events")
    event = LogEvent(level=LogLevel.WARNING, message="hardware warning")
    sink = StdlibLoggingSink(logger)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        sink.emit(event)

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert caplog.records[0].message == "hardware warning"
    assert caplog.records[0].lifecycle_event is event


def test_fan_out_event_sink_forwards_to_all_sinks_after_failure(caplog) -> None:
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

    with caplog.at_level(logging.ERROR, logger="lifecycle_pkg.events"):
        sink.emit(event)

    assert received == [event, event]
    assert "Lifecycle event sink" in caplog.text
