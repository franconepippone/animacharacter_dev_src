from typing import Callable, List, Generator
from collections.abc import Iterator
from .behavior import BehaviorInstance
from .actions import BehaviorActionType, BehaviorActionRaw
from .context import BehaviorContext

type BehaviorCoroutine = Iterator[BehaviorActionRaw]

class BehaviorExecutor:
    """
    Core engine that schedules and executes behaviors.
    """

    def __init__(self):
        self.behaviors: List[BehaviorInstance] = []
        self.tick_count = 0

    def add(self, behavior_fn: Callable[[BehaviorContext], BehaviorCoroutine], ctx: BehaviorContext, priority: int = 0):
        gen = behavior_fn(ctx)

        # Ensure it's a a valid object
        if not isinstance(gen, Iterator):
            raise TypeError("Behaviour fn must return an iterator")

        instance = BehaviorInstance(gen, priority)
        self.behaviors.append(instance)

        # keep execution order deterministic and based on priority
        self.behaviors.sort(key=lambda b: b.priority)

    def tick(self):
        """
        Ticks all running generator forward
        """
        self.tick_count += 1

        for b in tuple(self.behaviors):
            action = b.step(self.tick_count)

            if action is None:
                continue

            b.handle_action(action, self.tick_count)
            # if marked as done, remove it
            if b.done: self.behaviors.remove(b)