from typing import Callable, Generic, Iterator, TypeVar
from dataclasses import dataclass
from abc import ABC, abstractmethod
from .actions import BehaviorAction, BehaviorActionRaw, BehaviorActionType
from .context import BehaviorContext

ContextT = TypeVar("ContextT", bound=BehaviorContext)
BehaviorIterator = Iterator[BehaviorActionRaw | None]
BehaviorCallable = Callable[[ContextT], BehaviorIterator]

class AbstractBehavior(Generic[ContextT], ABC):
    """Base class for behaviors implemented with setup/tick methods."""

    def __init__(self, ctx: ContextT):
        self.ctx = ctx
        self._iterator = self._get_iterator()
    
    def _get_iterator(self) -> BehaviorIterator:
        """Build the internal iterator from setup() and tick()."""
        self.setup()
        while True:
            yield self.tick()
    
    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iterator)

    @abstractmethod
    def setup(self) -> BehaviorActionRaw | None:
        """Optional one-time initialization action."""
        ...

    @abstractmethod
    def tick(self) -> BehaviorActionRaw | None:
        """Return the next action for this behavior step."""
        ...

@dataclass
class BehaviorInstance:
    """Runtime wrapper for a behavior iterator and its scheduling state."""
    gen: BehaviorIterator 
    priority: int
    sleep_until: float = 0
    done: bool = False

    def step(self, time: float) -> None | BehaviorActionRaw:
        """Advance the behavior if it is awake and not done."""
        if self.done or time < self.sleep_until:
            return None

        try:
            action = next(self.gen)
        except StopIteration:
            return BehaviorAction.stop()

        return action

    def handle_action(self, action: BehaviorActionRaw, time: float):
        action_type, arg = action

        match action_type:
            case BehaviorActionType.CONTINUE:
                pass
            case BehaviorActionType.STOP:
                self.done = True
            case BehaviorActionType.SLEEP:
                self.sleep_until = max(0, time) + arg