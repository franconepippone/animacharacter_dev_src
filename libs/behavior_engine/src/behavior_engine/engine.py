from typing import Generic

from .behavior import BehaviorCallable, ContextT
from .executor import BehaviorExecutor, BehaviorInstance
from .registry import BehaviorEntry, BehaviorRegistry


class BehaviorEngine(Generic[ContextT]):
    """High-level engine that loads, plays, and inspects behaviors."""

    def __init__(self, ctx: ContextT):
        """Create the engine with a shared behavior context."""
        self.ctx = ctx
        self.registry = BehaviorRegistry()
        self.executor = BehaviorExecutor[ContextT](ctx)
        self._running: dict[str, tuple[BehaviorEntry, BehaviorInstance]] = {}

    def load_behavior(self, name: str, behavior: BehaviorCallable[ContextT], groups: list[str] | None = None, **metadata: object) -> BehaviorEntry:
        """Register a behavior under a name and optional groups."""
        return self.registry.register(name=name, behavior=behavior, groups=groups, **metadata)

    def get_behavior(self, name: str) -> BehaviorEntry:
        """Return the registered behavior entry for the given name."""
        return self.registry.get(name)

    def get_behaviors_by_group(self, group: str) -> list[BehaviorEntry]:
        """Return behaviors that belong to the requested group."""
        return self.registry.by_group(group)

    def get_behaviors_by_groups(self, *groups: str) -> list[BehaviorEntry]:
        """Return behaviors belonging to any of the given groups."""
        return self.registry.by_groups(*groups)

    def play_behavior(self, name: str, priority: int = 0):
        """Start a named behavior and track its running instance."""
        entry = self.registry.borrow(name)
        instance = self.executor.add(entry.behavior, priority)
        self._running[name] = (entry, instance)
        return instance

    def play_behavior_group(self, group: str, priority: int = 0) -> list[object]:
        """Start all behaviors in a group."""
        return [self.play_behavior(entry.name, priority) for entry in self.get_behaviors_by_group(group)]

    def stop_behavior(self, name: str) -> None:
        """Stop a running behavior and release it back to the registry."""
        if name not in self._running:
            return

        entry, instance = self._running.pop(name)
        self.executor.remove(instance)
        entry.borrowed = False

    def stop_all(self) -> None:
        """Stop every currently running behavior."""
        for name in list(self._running):
            self.stop_behavior(name)

    def is_running(self, name: str) -> bool:
        """Return True when a behavior is currently running."""
        return name in self._running

    def running_behaviors(self) -> list[str]:
        """Return the names of currently running behaviors."""
        return list(self._running)

    def loaded_behaviors(self) -> list[BehaviorEntry]:
        """Return all behaviors currently registered in the engine."""
        return self.registry.all()

    def tick(self) -> None:
        """Advance the engine one scheduler tick and clean up finished behaviors."""
        self.executor.tick()
        self._cleanup_finished()

    def _cleanup_finished(self) -> None:
        """Release any behaviors whose instances have finished or were removed."""
        for name, (entry, instance) in list(self._running.items()):
            if instance.done or instance not in self.executor.behaviors:
                self._running.pop(name)
                entry.borrowed = False
