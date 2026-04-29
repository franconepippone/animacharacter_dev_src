from typing import Iterator
from dataclasses import dataclass
from abc import ABC, abstractmethod
from .actions import BehaviorAction, BehaviorActionRaw, BehaviorActionType
from .context import BehaviorContext

from typing import Callable, Iterator

type BehaviorIterator  = Iterator[BehaviorActionRaw | None]
BehaviorCallable = Callable[[BehaviorContext], BehaviorIterator]

class AbstractBehavior(ABC):
    def __init__(self, ctx: BehaviorContext):
        self.ctx = ctx
        self._iterator = self._get_iterator()
    
    def _get_iterator(self) -> BehaviorIterator:
        self.setup()
        while True:
            yield self.tick()
    
    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iterator)

    @abstractmethod
    def setup(self) -> BehaviorActionRaw | None:
        ...

    @abstractmethod
    def tick(self) -> BehaviorActionRaw | None:
        ...

@dataclass
class BehaviorInstance:
    gen: BehaviorIterator 
    priority: int
    sleep_until: float = 0
    done = False

    def step(self, time: float) -> None | BehaviorActionRaw:
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