from __future__ import annotations

import functools
import time
import warnings
from abc import abstractmethod
from collections.abc import Callable, Iterable
from queue import Empty, Queue
from typing import Any, NamedTuple, TypeVar

from pydantic import TypeAdapter
from lifecycle_pkg import (
    FaultContext,
    Lifecyclable,
    RecoveryResult,
    TransitionResult,
)
from rclpy.logging import RcutilsLogger

from .databus import Databus, DataReader, DataWriter
from .utils import get_first_argument_type

_SPECIAL_PATH_CHARS = {"@"}
T = TypeVar("T")
ConfigHandler = Callable[[Any], Any]


def _cleanup_path(path: str) -> tuple[str, ...]:
    invalid = set(path) & _SPECIAL_PATH_CHARS
    if invalid:
        raise ValueError(f"Path contains invalid characters: {invalid}")
    return tuple(part for part in path.split("/") if part.strip())


def _fetch_dict_deep(
    data: dict[str, Any], keys: tuple[str, ...]
) -> tuple[bool, Any]:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


class ControllerException(Exception):
    """Deprecated base class for legacy controller-specific exceptions."""

    def __init__(self, code: int, description: str, *args: object) -> None:
        warnings.warn(
            "Controller-specific exceptions are deprecated; raise standard "
            "exceptions and use lifecycle recovery instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.code = code
        self.description = description
        super().__init__(*args)


class ControllerWarning(ControllerException):
    """Deprecated controller warning exception."""


class ControllerError(ControllerException):
    """Deprecated controller error exception."""


class ControllerFatal(ControllerException):
    """Deprecated controller fatal exception."""


class MotionCommand(NamedTuple):
    id: int
    value: float


class BaseHardwareController(Lifecyclable):
    """Lifecycle-managed interface for a hardware controller plugin.

    Plugins implement ``on_awake``, ``on_activate``, ``on_deactivate``,
    ``on_shutdown``, and ``on_recover``. Runtime work is performed by
    ``on_run``, which calls ``read``, config handlers, and ``control`` at
    ``flush_freq``.
    """

    _databus: Databus | None = None

    def __init__(
        self,
        name: str,
        flush_freq: float,
        command_group: Iterable[int] = (),
    ) -> None:
        if flush_freq <= 0:
            raise ValueError(f"flush_freq must be positive, got {flush_freq}")
        self.name = name
        self.flush_freq = flush_freq
        self.command_group = set(command_group)
        self._config_handlers: dict[tuple[str, ...], ConfigHandler] = {}
        self._input_commands: Queue[MotionCommand] = Queue()
        self._cfg_updates_queue: Queue[dict[str, Any]] = Queue()
        self.logger = RcutilsLogger(f"HWController-{self.name}")

    def create_databus_writer(
        self, topic: str, data_type: type[T], initial: T
    ) -> DataWriter[T]:
        """Create a writer on the shared databus during plugin construction."""
        if not isinstance(self._databus, Databus):
            raise RuntimeError("The controller databus has not been initialized")
        return self._databus.create_writer(topic, data_type, initial)

    def create_databus_reader(
        self, topic: str, data_type: type[T]
    ) -> DataReader[T]:
        """Create a reader on the shared databus during plugin construction."""
        if not isinstance(self._databus, Databus):
            raise RuntimeError("The controller databus has not been initialized")
        return self._databus.create_reader(topic, data_type)

    def subscribe_to_command_group(self, ids_group: Iterable[int]) -> None:
        """Set the command IDs routed to this controller."""
        self.command_group = set(ids_group)

    def enqueue_command(self, command: MotionCommand) -> None:
        """Queue a motion command for the next runtime tick."""
        self._input_commands.put(command)

    def enqueue_config_update(self, config: dict[str, Any]) -> None:
        """Queue configuration data for handlers on the next runtime tick."""
        self._cfg_updates_queue.put(config)

    def clear_pending_work(self) -> None:
        """Discard commands and config updates left over after shutdown."""
        for work_queue in (self._input_commands, self._cfg_updates_queue):
            while True:
                try:
                    work_queue.get_nowait()
                except Empty:
                    break

    def subscribe_to_config_path(
        self,
        path: str,
        handler: ConfigHandler,
        enforce_type: bool = False,
    ) -> None:
        """Register a handler for a path in incoming configuration dictionaries."""
        parts = _cleanup_path(path)
        if parts in self._config_handlers:
            self.logger.warning(f"Overriding config handler for '{path}'")

        if enforce_type:
            arg_type = get_first_argument_type(handler)
            if arg_type is not None:
                adapter = TypeAdapter(arg_type)
                original_handler = handler

                @functools.wraps(handler)
                def validated_handler(config: Any, *args: Any, **kwargs: Any) -> Any:
                    return original_handler(
                        adapter.validate_python(config), *args, **kwargs
                    )

                handler = validated_handler

        self._config_handlers[parts] = handler

    def _execute_queued_config_updates(self) -> None:
        count = self._cfg_updates_queue.qsize()
        for _ in range(count):
            try:
                config = self._cfg_updates_queue.get_nowait()
            except Empty:
                break
            self._dispatch_config(config)

    def _dispatch_config(self, global_config: dict[str, Any]) -> None:
        for path_parts, handler in self._config_handlers.items():
            found, subconfig = _fetch_dict_deep(global_config, path_parts)
            if found:
                handler(subconfig)

    def read(self) -> None:
        """Optionally poll hardware for incoming data before controlling it."""

    def on_run(self) -> TransitionResult:
        """Run one read/config/control tick at the configured frequency."""
        started = time.perf_counter()
        command_count = self._input_commands.qsize()
        commands: list[MotionCommand] = []
        for _ in range(command_count):
            try:
                commands.append(self._input_commands.get_nowait())
            except Empty:
                break

        self._execute_queued_config_updates()
        self.read()
        self.control(commands)

        remaining = (1.0 / self.flush_freq) - (time.perf_counter() - started)
        if remaining > 0:
            time.sleep(remaining)
        return TransitionResult.SUCCESS

    @abstractmethod
    def control(self, commands: list[MotionCommand]) -> None:
        """Apply the queued motion commands to the hardware."""
        raise NotImplementedError

    @abstractmethod
    def on_awake(self) -> TransitionResult:
        """Prepare hardware for inactive operation."""
        raise NotImplementedError

    @abstractmethod
    def on_activate(self) -> TransitionResult:
        """Enable active hardware operation."""
        raise NotImplementedError

    @abstractmethod
    def on_deactivate(self) -> TransitionResult:
        """Disable active hardware operation."""
        raise NotImplementedError

    @abstractmethod
    def on_shutdown(self) -> TransitionResult:
        """Release hardware resources."""
        raise NotImplementedError

    @abstractmethod
    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        """Recover from a failed lifecycle operation or runtime tick."""
        raise NotImplementedError
