"""Generic dispatcher for routing keyed commands to handlers.

This module defines a small `Dispatcher` class that associates arbitrary
keys with callables and forwards incoming commands to the appropriate
handler. It is intentionally minimal: no concurrency, no scheduling, and
no assumptions about the structure of the command payload.

Concepts:
- A command is represented as a `(key, payload)` tuple. The dispatcher
  does not interpret either element.
- Handlers receive only the payload. Any additional parsing or validation
  is the handler's responsibility.
- The dispatcher performs simple synchronous routing. If a handler blocks,
  the entire dispatch call blocks as well.
"""

from typing import Dict, Callable, Tuple, Iterable, Any, Generic, TypeVar, TypeAlias

KEY_T = TypeVar("KEY_T")
PAYLOAD_T = TypeVar("PAYLOAD_T")

Handler: TypeAlias = Callable[[PAYLOAD_T], Any]
Command: TypeAlias = Tuple[KEY_T, Any]


class Dispatcher(Generic[KEY_T, PAYLOAD_T]):
    """Associate keys with handlers and route commands to them.

    The dispatcher maintains a mapping from keys to handler callables.
    When commands are dispatched, the dispatcher looks up the handler for
    each command's key and invokes it with the payload. Commands whose
    keys have no registered handler are ignored.

    This class is not thread-safe. External synchronization is required
    if multiple threads mutate the handler map or shared memory by the handlers.
    """

    def __init__(self):
        """Initialize an empty dispatcher with no registered handlers."""
        self.map: Dict[KEY_T, Handler] = {}

    def get_map_size(self) -> int:
        """The amount of handlers registered."""
        return len(self.map)

    def clear_handlers(self):
        """Remove all registered handlers.

        After clearing, no commands will be routed until new handlers are
        registered.
        """
        self.map.clear()

    def register_handler(self, key: KEY_T, handler: Handler):
        """Register or replace a handler for a given key.

        Args:
            key: Identifier used to select the handler.
            handler: Callable invoked with the command payload.
        """
        self.map[key] = handler

    def dispatch_multiple(self, commands: Iterable[Command]):
        """Dispatch a sequence of commands.

        Each command is a `(key, payload)` tuple. If a handler is
        registered for the key, it is invoked with the payload. Commands
        with unregistered keys are skipped.
        """
        handlers = self.map
        for key, payload in commands:
            handler = handlers.get(key)
            if handler:
                handler(payload)

    def dispatch(self, command: Command):
        """Dispatch a single command.

        Args:
            command: A `(key, payload)` tuple.

        If no handler is registered for the key, nothing happens.
        """
        key, payload = command
        handler = self.map.get(key)
        if handler:
            handler(payload)