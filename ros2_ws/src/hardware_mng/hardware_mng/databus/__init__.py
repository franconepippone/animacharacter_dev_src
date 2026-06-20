"""
Lightweight typed single-process publish/subscribe databus.

This module provides a minimal shared-state messaging system based on topics.
Each topic stores:
- the latest published value
- a monotonically increasing sequence number

The system is designed around:
- one writer per topic
- many readers per topic
- initialization-time validation
- stable runtime topology
- lock-free runtime reads and writes

Typical usage:
- create readers/writers during initialization
- call finalize()
- use readers/writers during runtime

Thread safety:
- this implementation relies on CPython atomic reference assignment semantics
  and the GIL
- topic updates are atomic because the entire topic state tuple is replaced
- readers always observe a coherent (value, seqnum) snapshot
- readers may safely read concurrently with writers

IMPORTANT:
Published payload objects must be treated as immutable after write().

This system does NOT protect payload contents from concurrent mutation.
Mutating a published payload object may cause:
- readers observing state changes without seqnum updates
- data races on payload internals
- undefined synchronization behavior

For best results, payloads should be:
- frozen dataclasses
- tuples containing immutable values
- immutable custom classes
- primitive immutable types
"""

from __future__ import annotations

from typing import Any, Type, Generic, TypeVar
from dataclasses import dataclass



class DatabusError(Exception): ...
class DatabusTopologyError(DatabusError): ...


def normalize_topic(name: str) -> str:
    """Normalize a topic name before registration or lookup."""
    return name

DatabusMsgType = TypeVar('DatabusMsgType')

type TopicState = tuple[Any, int]

@dataclass(slots=True)
class DatabusTopic(Generic[DatabusMsgType]):
    """
    Internal databus topic state container.

    Stores:
    - latest published value
    - sequence number
    - associated message type

    Topic state updates are atomic because the entire state tuple is replaced
    instead of mutating fields independently.
    """

    name: str
    _state: TopicState
    _msg_type: Type[DatabusMsgType]

    def __hash__(self) -> int:
        return id(self.name)

    def set_val(self, new_val: DatabusMsgType):
        """
        Publish a new value to this topic.

        Increments the sequence number automatically.
        """
        self._state = (new_val, self._state[1] + 1) # atomic write, dont need locks

    @property
    def seqnum(self) -> int:
        """Current topic sequence number."""
        return self._state[1]

class DataWriter(Generic[DatabusMsgType]):
    """
    Topic write endpoint.

    Usage:
        writer.write(value)

    Writers own a topic exclusively. Only one writer may exist per topic.

    Published payloads are expected to be immutable after write().
    Writers are trusted to respect topic type correctness and payload
    immutability rules.
    """

    def __init__(self, target: DatabusTopic[DatabusMsgType], msg_type: Type[DatabusMsgType], initial: DatabusMsgType):
        self._msg_type = msg_type
        self._target_topic = target
        self.write(initial)
    
    def write(self, value: DatabusMsgType):
        """
        Write a new value to the bus.

        Writers are trusted to publish values matching the declared topic type.

        NOTE: Payload objects must NOT be mutated after publication.
        Mutating published objects may bypass sequence tracking and produce
        undefined synchronization behavior for readers.
        """
        self._target_topic.set_val(value)

class DataReader(Generic[DatabusMsgType]):
    """
    Topic read endpoint.

    Usage:
        if reader.has_update():
            value = reader.read()

    Readers track the last observed sequence number locally.
    """

    def __init__(self, source: DatabusTopic[DatabusMsgType], msg_type: Type[DatabusMsgType]):
        self._msg_type = msg_type
        self._source_topic = source
        self._last_seq = 0

    def has_update(self) -> bool:
        """
        Check whether data changed since the last read.
        """
        # if the data has not changed since last read
        return self._source_topic.seqnum > self._last_seq

    def read(self) -> DatabusMsgType:
        """
        Read the latest data value.

        Reading also updates the reader's internal sequence tracking state.
        """
        value, self._last_seq = self._source_topic._state # is this atomic?
        return value



class Databus:
    """
    Databus topology manager.

    Usage:
    ```python
        bus = Databus()

        pose_writer = bus.create_writer(
            'robot/pose',
            tuple,
            (0.0, 0.0)
        )

        pose_reader = bus.create_reader(
            'robot/pose',
            tuple
        )

        bus.finalize()

        pose_writer.write((1.0, 2.0))

        if pose_reader.has_update():
            pose = pose_reader.read()
    ```
    The databus validates:
    - topic existence
    - topic type consistency
    - single-writer ownership
    - finalized topology validity

    After finalize(), topology changes are forbidden.
    """

    def __init__(self):
        self.topics: dict[str, DatabusTopic] = {}
        # tracks topics that own a writer
        self._writer_topics: set[DatabusTopic] = set()

        self._finalized = False

    def _assert_topics_have_writers(self):
        for topic in self.topics.values():
            if topic not in self._writer_topics:
                raise DatabusTopologyError(f'Topic "{topic.name}" has no writer')
    
    def finalize(self) -> None:
        """
        Finalize the databus topology.

        After finalization:
        - no new readers/writers may be created
        - all topics must already own a writer (if enforce_writers is True)
        """
        self._assert_topics_have_writers()
        self._finalized = True
    
    def _require_unfinalized(self):
        if self._finalized:
            raise DatabusError('Operation unsupported after bus finaliziation occured')
    
    def _require_topic(self, name: str, msg_type: Type[DatabusMsgType]) -> DatabusTopic[DatabusMsgType]:
        if not name in self.topics:
            self.topics[name] = DatabusTopic(name, (None, 0), msg_type)
        
        topic = self.topics[name]
        if topic._msg_type != msg_type:
            raise DatabusTopologyError(f'Topic \'{topic.name}\' message type mismatch: got "{msg_type}", but topic is of type is "{topic._msg_type}"')
        return self.topics[name]

    def _register_writer(self, writer: DataWriter):
        topic = writer._target_topic

        if topic in self._writer_topics:
            raise DatabusTopologyError(f'Topic "{topic.name}" can only have one writer')

        self._writer_topics.add(topic)
    
    # API

    def create_writer(self, topic_name: str, topic_msg_type: Type[DatabusMsgType], initial: DatabusMsgType) -> DataWriter[DatabusMsgType]:
        """
        Create and register a topic writer.

        Creating a writer also initializes the topic value.
        """
        if not isinstance(initial, topic_msg_type):
            raise DatabusError(f'Initial value provided to writer of \'{topic_name}\' is not of the declared type: {topic_msg_type}')
        self._require_unfinalized()
        topic = self._require_topic(topic_name, topic_msg_type)
        writer = DataWriter(topic, topic_msg_type, initial)
        self._register_writer(writer)
        return writer
    
    def create_reader(self, topic_name: str, topic_msg_type: Type[DatabusMsgType]) -> DataReader[DatabusMsgType]:
        """
        Create and register a topic reader.

        Readers may only attach to topics with matching message types.
        """
        self._require_unfinalized()
        topic = self._require_topic(topic_name, topic_msg_type)
        reader = DataReader(topic, topic_msg_type)
        return reader



if __name__ == "__main__":

    print("\n--- BASIC READ/WRITE TEST ---")

    bus = Databus()

    pose_writer = bus.create_writer(
        "robot/pose",
        tuple,
        (0.0, 0.0),
    )

    pose_reader = bus.create_reader(
        "robot/pose",
        tuple,
    )

    bus.finalize()

    print("Initial update available:", pose_reader.has_update())

    print("Initial read:", pose_reader.read())

    print("Update available after read:", pose_reader.has_update())

    pose_writer.write((1.0, 2.0))

    print("Update available after write:", pose_reader.has_update())

    print("Updated read:", pose_reader.read())

    print("Update available after second read:", pose_reader.has_update())


    print("\n--- MULTI TOPIC TEST ---")

    bus = Databus()

    int_writer = bus.create_writer(
        "counter",
        int,
        0,
    )

    str_writer = bus.create_writer(
        "status",
        str,
        "boot",
    )

    int_reader = bus.create_reader(
        "counter",
        int,
    )

    str_reader = bus.create_reader(
        "status",
        str,
    )

    bus.finalize()

    int_writer.write(42)
    str_writer.write("running")

    print("Counter:", int_reader.read())
    print("Status:", str_reader.read())


    print("\n--- SEQUENCE TRACKING TEST ---")

    bus = Databus()

    writer = bus.create_writer(
        "tick",
        int,
        0,
    )

    reader = bus.create_reader(
        "tick",
        int,
    )

    bus.finalize()

    for i in range(5):
        writer.write(i)

    print("Reader sees update:", reader.has_update())

    print("Latest value:", reader.read())

    print("Reader sees update after read:", reader.has_update())


    print("\n--- TYPE VALIDATION TEST ---")

    try:
        bus = Databus()

        bus.create_writer(
            "value",
            int,
            123,
        )

        bus.create_reader(
            "value",
            str,
        )

        print("FAILED: type mismatch was not detected")

    except RuntimeError as e:
        print("PASSED:", e)


    print("\n--- SINGLE WRITER VALIDATION TEST ---")

    try:
        bus = Databus()

        bus.create_writer(
            "topic",
            int,
            0,
        )

        bus.create_writer(
            "topic",
            int,
            1,
        )

        print("FAILED: duplicate writer was not detected")

    except RuntimeError as e:
        print("PASSED:", e)


    print("\n--- FINALIZATION TEST ---")

    try:
        bus = Databus()

        bus.create_writer(
            "value",
            int,
            0,
        )

        bus.finalize()

        bus.create_reader(
            "another",
            int,
        )

        print("FAILED: post-finalize mutation was not blocked")

    except RuntimeError as e:
        print("PASSED:", e)


    print("\n--- MISSING WRITER TEST ---")

    try:
        bus = Databus()

        bus.create_reader(
            "orphan_topic",
            int,
        )

        bus.finalize()

        print("FAILED: missing writer was not detected")

    except RuntimeError as e:
        print("PASSED:", e)