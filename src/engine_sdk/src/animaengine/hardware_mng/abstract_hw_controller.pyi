from abc import abstractmethod
from collections.abc import Callable, Iterable
from typing import Any, NamedTuple, TypeVar

from lifecycle_pkg import FaultContext, Lifecyclable, RecoveryResult, TransitionResult
from rclpy.logging import RcutilsLogger

from .databus import Databus, DataReader, DataWriter


T = TypeVar("T")


class MotionCommand(NamedTuple):
    id: int
    value: float


class BaseHardwareController(Lifecyclable):
    """Lifecycle-managed base class for a hardware controller plugin.

    Every plugin class must define a no-argument ``__init__`` and call
    ``super().__init__(name, flush_freq)``. The hardware manager creates one
    shared :class:`Databus` before constructing plugins and finalizes its
    topology before starting their lifecycle runners. Create databus readers
    and writers in the constructor; topics have one writer, and published
    payloads must be treated as immutable.

    Implement lifecycle hooks for device setup, activation, shutdown, and
    recovery. Runtime ticks dispatch configuration updates, call ``read`` and
    ``control``, and maintain the configured ``flush_freq``.
    """

    _databus: Databus | None
    name: str
    flush_freq: float
    command_group: set[int]
    logger: RcutilsLogger

    def __init__(
        self,
        name: str,
        flush_freq: float,
        command_group: Iterable[int] = ...,
    ) -> None: ...

    def create_databus_writer(
        self,
        topic: str,
        data_type: type[T],
        initial: T,
    ) -> DataWriter[T]: ...

    def create_databus_reader(
        self,
        topic: str,
        data_type: type[T],
    ) -> DataReader[T]: ...

    def subscribe_to_command_group(self, ids_group: Iterable[int]) -> None: ...

    def enqueue_command(self, command: MotionCommand) -> None: ...

    def enqueue_config_update(self, config: dict[str, Any]) -> None: ...

    def clear_pending_work(self) -> None: ...

    def subscribe_to_config_path(
        self,
        path: str,
        handler: Callable[[Any], Any],
        enforce_type: bool = False,
    ) -> None: ...

    def read(self) -> None: ...

    def on_run(self) -> TransitionResult: ...

    @abstractmethod
    def control(self, commands: list[MotionCommand]) -> None: ...

    @abstractmethod
    def on_awake(self) -> TransitionResult: ...

    @abstractmethod
    def on_activate(self) -> TransitionResult: ...

    @abstractmethod
    def on_deactivate(self) -> TransitionResult: ...

    @abstractmethod
    def on_shutdown(self) -> TransitionResult: ...

    @abstractmethod
    def on_recover(self, fault: FaultContext) -> RecoveryResult: ...
