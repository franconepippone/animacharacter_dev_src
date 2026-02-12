from contextlib import AbstractContextManager, contextmanager
from typing import TypeVar, Generic, Callable, Iterable, Dict, Set, List, Tuple, Optional, Any

from .dispatcher import Dispatcher

KEY_T = TypeVar("KEY_T")
VAL_T = TypeVar("VAL_T")

Handler = Callable[[VAL_T], Any]
Command = Tuple[KEY_T, VAL_T]


class BatchDispatcher(Generic[KEY_T, VAL_T]):
    """
    Wraps a Dispatcher and batches commands by key sets.

    To add a batch, call 'add_batch'.  

    Each batch is dispatched inside an optional context manager, which can handle setup
    and teardown logic for the entire batch.
    """

    def __init__(self, dispatcher: Dispatcher[KEY_T, VAL_T]):
        self.dispatcher = dispatcher
        # Each batch: (key set, optional context manager)
        self.batches: List[Tuple[Set[KEY_T], Optional[AbstractContextManager]]] = []

    def add_batch(
        self,
        key_set: Set[KEY_T],
        context: Optional[AbstractContextManager] = None,
    ):
        """
        Add a batch of keys and an optional context manager to wrap the dispatch.
        """
        self.batches.append((key_set, context))

    def dispatch(self, commands: Iterable[Command]):
        """
        Dispatch commands grouped by batch sets inside their context managers.
        """
        batch_commands: List[List[Command]] = [[] for _ in self.batches]
        unbatched_commands: List[Command] = [] # for commands who are not in any batch

        # Single pass over commands
        for key, val in commands:
            found = False
            for i, (key_set, _) in enumerate(self.batches):
                if key in key_set:
                    batch_commands[i].append((key, val))
                    found = True
            if not found:
                unbatched_commands.append((key, val))

        # Dispatch each batch inside its context manager
        for (key_set, context), cmds in zip(self.batches, batch_commands):
            if not cmds:
                continue
            if context is not None:
                with context:
                    self.dispatcher.dispatch_multiple(cmds)
            else:
                self.dispatcher.dispatch_multiple(cmds)
        
        if len(unbatched_commands) > 0:
            self.dispatcher.dispatch_multiple(unbatched_commands)


# ---- Helper to build a context manager from pre/post hooks ----
@contextmanager
def hooks_to_context(pre_hook: Optional[Callable[[], Any]] = None,
                     post_hook: Optional[Callable[[], Any]] = None):
    if pre_hook: pre_hook()
    yield
    if post_hook: post_hook()
