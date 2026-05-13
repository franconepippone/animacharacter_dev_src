import time
import threading
from typing import Generic, Dict
from collections.abc import Iterator

from .behavior import (
    BehaviorInstance,
    BehaviorCallable,
    ContextT,
)
from .actions import (
    BehaviorActionType,
    BehaviorActionRaw,
)


class BehaviorThread(Generic[ContextT]):
    """
    Runs a single behavior instance inside its own deterministic thread.

    The behavior itself controls timing semantics by yielding actions:
        - CONTINUE -> resume immediately
        - SLEEP    -> sleep relative duration
        - TICK     -> periodic phase-locked execution
        - STOP     -> terminate behavior
    """

    def __init__(self, instance: BehaviorInstance, ctx: ContextT):
        self.instance = instance
        self.ctx = ctx

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"BehaviorThread-{id(instance)}"
        )

        self._running = False

        # state for periodic scheduling
        self._tick_period = None
        self._next_tick = None

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def join(self, timeout=None):
        self._thread.join(timeout)

    def _run(self):
        while self._running and not self.instance.done:
            now = time.monotonic()

            # synchronize context time for this behavior iteration
            self.ctx.time._sync_time = now

            action = self.instance.step(now)

            if action is None:
                action = (BehaviorActionType.CONTINUE, 0)

            self._handle_action(action)

    def _handle_action(self, action: BehaviorActionRaw):
        action_type, arg = action

        if action_type == BehaviorActionType.STOP:
            self.instance.done = True
            self._running = False
            return

        if action_type == BehaviorActionType.CONTINUE:
            return

        if action_type == BehaviorActionType.SLEEP:
            time.sleep(max(0.0, arg))
            return

        if action_type == BehaviorActionType.TICK:
            self._tick_sleep(arg)
            return

    def _tick_sleep(self, freq: float):
        """
        Deterministic periodic scheduling.

        Maintains phase continuity:
            next_tick += period

        instead of:
            next_tick = now + period

        which avoids long-term drift.
        """

        if freq <= 0:
            return

        period = 1.0 / freq
        now = time.monotonic()

        # frequency changed dynamically
        if self._tick_period != period:
            self._tick_period = period
            self._next_tick = now + period

        # initialize
        if self._next_tick is None:
            self._next_tick = now + period

        sleep_time = self._next_tick - now

        if sleep_time > 0:
            time.sleep(sleep_time)

        # preserve phase continuity
        self._next_tick += period

        # recover from severe overruns
        now_after = time.monotonic()

        if self._next_tick < now_after:
            self._next_tick = now_after + period


class DeterministicExecutor(Generic[ContextT]):
    """
    Deterministic executor.

    Each behavior runs inside its own dedicated thread with
    independent timing guarantees.

    The API intentionally mirrors BehaviorExecutor.
    """

    def __init__(self, ctx: ContextT):
        self.ctx = ctx
        self.behaviors: Dict[BehaviorInstance, BehaviorThread] = {}

    def add(
        self,
        behavior_fn: BehaviorCallable[ContextT],
        priority: int = 0
    ) -> BehaviorInstance:

        gen = behavior_fn(self.ctx)

        if not isinstance(gen, Iterator):
            raise TypeError("Behaviour fn must return an iterator")

        instance = BehaviorInstance(gen, priority)

        runner = BehaviorThread(instance, self.ctx)

        self.behaviors[instance] = runner
        runner.start()

        return instance

    def remove(self, instance: BehaviorInstance):
        runner = self.behaviors.pop(instance, None)

        if runner is not None:
            runner.stop()
            runner.join()

    def shutdown(self):
        for runner in self.behaviors.values():
            runner.stop()

        for runner in self.behaviors.values():
            runner.join()

        self.behaviors.clear()