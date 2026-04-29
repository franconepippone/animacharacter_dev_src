from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, Sequence, TypeVar, cast

from .behavior import AbstractBehavior, BehaviorCallable, ContextT
from .context import BehaviorContext

ContextTV = TypeVar("ContextTV", bound=BehaviorContext, covariant=True)


class BehaviorEngineLike(Protocol[ContextTV]):
    def load_behavior(
        self,
        name: str,
        behavior: BehaviorCallable[ContextTV],
        groups: list[str] | None = None,
        **metadata: Any,
    ) -> Any:
        ...


@dataclass(frozen=True)
class BehaviorPlugin:
    name: str
    behavior: Any
    groups: tuple[str, ...]
    metadata: dict[str, Any]


def behavior(name: str, groups: Sequence[str] | None = None, **metadata: Any):
    """Decorator for registering a behavior inside a plugin module."""

    def decorator(target: Any) -> Any:
        plugin = BehaviorPlugin(
            name=name,
            behavior=target,
            groups=tuple(groups or []),
            metadata=dict(metadata),
        )
        setattr(target, "_behavior_plugin", plugin)
        return target

    return decorator


def discover_behaviors(module: ModuleType) -> list[BehaviorPlugin]:
    """Return all decorated behaviors found in a module."""
    plugins: list[BehaviorPlugin] = []
    for value in vars(module).values():
        plugin = getattr(value, "_behavior_plugin", None)
        if isinstance(plugin, BehaviorPlugin):
            plugins.append(plugin)
    return plugins


def _make_callable(behavior: Any) -> BehaviorCallable[ContextT]:
    if isinstance(behavior, type) and issubclass(behavior, AbstractBehavior):
        def wrapper(ctx: ContextT):
            return behavior(ctx)

        return cast(BehaviorCallable[ContextT], wrapper)

    return cast(BehaviorCallable[ContextT], behavior)


def load_behaviors_from_module(engine: BehaviorEngineLike[ContextTV], module: ModuleType) -> list[object]:
    """Load all decorated behaviors from a loaded module into the engine."""
    entries: list[object] = []
    for plugin in discover_behaviors(module):
        entry = engine.load_behavior(
            name=plugin.name,
            behavior=_make_callable(plugin.behavior),
            groups=list(plugin.groups) if plugin.groups else None,
            **plugin.metadata,
        )
        entries.append(entry)
    return entries


def _make_module_name(path: Path, module_name: str | None = None) -> str:
    if module_name:
        return module_name
    return f"behavior_plugin_{path.stem}_{uuid.uuid4().hex}"


def load_behaviors_from_file(engine: BehaviorEngineLike[ContextTV], path: str | Path, module_name: str | None = None) -> list[object]:
    """Load a Python file containing decorated behaviors into the engine."""
    path = Path(path)
    name = _make_module_name(path, module_name)
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load plugin file from {path}")

    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    return load_behaviors_from_module(engine, module)


def load_behaviors_from_directory(
    engine: BehaviorEngineLike[ContextTV],
    directory: str | Path,
    pattern: str = "*.py",
    recursive: bool = False,
) -> list[object]:
    """Load all plugin Python files from a directory into the engine."""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory!r} is not a directory")

    entries: list[object] = []
    matcher = directory.rglob if recursive else directory.glob
    for path in sorted(matcher(pattern)):
        if path.name.startswith("_"):
            continue
        if path.is_file():
            entries.extend(load_behaviors_from_file(engine, path))
    return entries
