from _typeshed import Incomplete
from dataclasses import dataclass
from typing import Any, Generic, Type, TypeVar
class DatabusError(Exception): ...
class DatabusTopologyError(DatabusError): ...
def normalize_topic(name: str) -> str:
    """Normalize a topic name before registration or lookup."""
DatabusMsgType = TypeVar('DatabusMsgType')
TopicState = tuple[Any, int]
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
    def __hash__(self) -> int: ...
    def set_val(self, new_val: DatabusMsgType):
        """
        Publish a new value to this topic.

        Increments the sequence number automatically.
        """
    @property
    def seqnum(self) -> int:
        """Current topic sequence number."""
    def __init__(self, name, _state, _msg_type) -> None: ...
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
    def __init__(self, target: DatabusTopic[DatabusMsgType], msg_type: Type[DatabusMsgType], initial: DatabusMsgType) -> None: ...
    def write(self, value: DatabusMsgType):
        """
        Write a new value to the bus.

        Writers are trusted to publish values matching the declared topic type.

        NOTE: Payload objects must NOT be mutated after publication.
        Mutating published objects may bypass sequence tracking and produce
        undefined synchronization behavior for readers.
        """
class DataReader(Generic[DatabusMsgType]):
    """
    Topic read endpoint.

    Usage:
        if reader.has_update():
            value = reader.read()

    Readers track the last observed sequence number locally.
    """
    def __init__(self, source: DatabusTopic[DatabusMsgType], msg_type: Type[DatabusMsgType]) -> None: ...
    def has_update(self) -> bool:
        """
        Check whether data changed since the last read.
        """
    def read(self) -> DatabusMsgType:
        """
        Read the latest data value.

        Reading also updates the reader's internal sequence tracking state.
        """
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
    topics: Incomplete
    def __init__(self) -> None: ...
    def finalize(self) -> None:
        """
        Finalize the databus topology.

        After finalization:
        - no new readers/writers may be created
        - all topics must already own a writer (if enforce_writers is True)
        """
    def create_writer(self, topic_name: str, topic_msg_type: Type[DatabusMsgType], initial: DatabusMsgType) -> DataWriter[DatabusMsgType]:
        """
        Create and register a topic writer.

        Creating a writer also initializes the topic value.
        """
    def create_reader(self, topic_name: str, topic_msg_type: Type[DatabusMsgType]) -> DataReader[DatabusMsgType]:
        """
        Create and register a topic reader.

        Readers may only attach to topics with matching message types.
        """
