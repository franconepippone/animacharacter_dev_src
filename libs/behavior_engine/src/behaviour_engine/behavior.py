from typing import Any, Iterator
from .actions import BehaviorAction, BehaviorActionRaw, BehaviorActionType

type BehaviorCoroutine = Iterator[BehaviorActionRaw | None]

class BehaviorInstance:
    def __init__(self, gen: BehaviorCoroutine, priority: int = 0):
        self.gen = gen
        self.priority = priority

        self.sleep_until = 0
        self.done = False

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
                self.sleep_until = time + arg