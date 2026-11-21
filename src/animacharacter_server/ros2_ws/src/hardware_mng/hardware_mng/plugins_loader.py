from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, cast

from .abstract_hw_controller import BaseHardwareController
from .databus import Databus


@dataclass(frozen=True)
class PluginLoadIssue:
    """A controller path or plugin directory that could not be loaded."""

    source: str
    message: str


def register_plugin_dirs(plugin_dirs: list[str]) -> list[PluginLoadIssue]:
    """Add existing plugin directories to the Python module search path."""
    issues: list[PluginLoadIssue] = []
    for directory in plugin_dirs:
        path = Path(directory).expanduser()
        if not path.is_dir():
            issues.append(
                PluginLoadIssue(directory, "plugin directory does not exist")
            )
            continue
        resolved = str(path.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    return issues


def import_module(path: str) -> ModuleType:
    """Import a controller module by its Python module path."""
    try:
        return importlib.import_module(path)
    except Exception as error:
        raise RuntimeError(
            f"Failed to import hardware controller module '{path}': {error}"
        ) from error


def import_class(path: str) -> Callable[[], BaseHardwareController]:
    """Import a no-argument controller class using ``module:ClassName`` syntax."""
    module_path, separator, class_name = path.partition(":")
    if not separator or not module_path or not class_name or ":" in class_name:
        raise ValueError(
            f"Invalid controller path '{path}'; expected 'module.path:ClassName'"
        )

    module = import_module(module_path)
    controller_class = getattr(module, class_name, None)
    if not inspect.isclass(controller_class):
        raise TypeError(
            f"'{class_name}' in module '{module_path}' is not a class"
        )
    if not issubclass(controller_class, BaseHardwareController):
        raise TypeError(
            f"'{path}' is not a subclass of BaseHardwareController"
        )
    return cast(Callable[[], BaseHardwareController], controller_class)


def load_controllers(
    controller_paths: list[str],
    plugin_dirs: list[str],
    databus: Databus,
) -> tuple[list[BaseHardwareController], list[PluginLoadIssue]]:
    """Load no-argument controller plugins, returning per-path failures.

    Plugin classes must define ``__init__(self)`` and initialize their base
    controller with its name and run frequency.
    """
    issues = register_plugin_dirs(plugin_dirs)
    BaseHardwareController._databus = databus
    controllers: list[BaseHardwareController] = []

    for path in controller_paths:
        try:
            controller_class = import_class(path)
            controllers.append(controller_class())
        except Exception as error:
            issues.append(PluginLoadIssue(path, str(error)))

    return controllers, issues
