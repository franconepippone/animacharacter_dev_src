from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Sequence

from .behavior import BehaviorCallable, ContextT

@dataclass
class BehaviorEntry:
    """Registry record for a named behavior and its metadata."""
    name: str
    behavior: BehaviorCallable
    groups: tuple[str, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)
    borrowed: bool = False

    def __post_init__(self):
        self.groups = tuple(self.groups)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "behavior": self.behavior,
            "groups": self.groups,
            "metadata": dict(self.metadata),
            "borrowed": self.borrowed,
        }


class BehaviorRegistry:
    """Store behaviors by name and group for lookup and borrowing."""

    def __init__(self):
        """Create an empty behavior registry."""
        self._entries: Dict[str, BehaviorEntry] = {}
        self._groups: Dict[str, set[str]] = {}

    def register(
        self,
        name: str,
        behavior: BehaviorCallable[ContextT],
        groups: Sequence[str] | None = None,
        **metadata: Any,
    ) -> BehaviorEntry:
        """Register a named behavior with optional groups and metadata."""
        if name in self._entries:
            raise KeyError(f"Behavior '{name}' is already registered")

        entry = BehaviorEntry(name=name, behavior=behavior, groups=tuple(groups or []), metadata=metadata)
        self._entries[name] = entry

        for group in entry.groups:
            self._groups.setdefault(group, set()).add(name)

        return entry

    def get(self, name: str) -> BehaviorEntry:
        """Return the behavior entry for the given name."""
        return self._entries[name]

    def get_optional(self, name: str) -> BehaviorEntry | None:
        """Return the named behavior entry, or None if it is not registered."""
        return self._entries.get(name)

    def by_group(self, group: str) -> list[BehaviorEntry]:
        """Return all behavior entries registered in the given group."""
        return [self._entries[name] for name in sorted(self._groups.get(group, []))]

    def by_groups(self, *groups: str) -> list[BehaviorEntry]:
        """Return entries appearing in any of the provided groups."""
        names: set[str] = set()
        for group in groups:
            names.update(self._groups.get(group, []))
        return [self._entries[name] for name in sorted(names)]

    def all(self) -> list[BehaviorEntry]:
        """Return all registered behavior entries."""
        return list(self._entries.values())

    def borrow(self, name: str) -> BehaviorEntry:
        """Mark a behavior as borrowed and return its entry."""
        entry = self.get(name)
        if entry.borrowed:
            raise RuntimeError(f"Behavior '{name}' is already borrowed")
        entry.borrowed = True
        return entry

    def release(self, name: str) -> None:
        """Release a borrowed behavior so it can be used again."""
        entry = self.get(name)
        entry.borrowed = False
