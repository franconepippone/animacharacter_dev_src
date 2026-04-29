"""Behavior engine package.

This package provides the runtime building blocks for loading, registering,
executing, and inspecting behaviors.

A behavior is a coroutine-like object that yields actions to control the
scheduler. Behaviors can be generator functions or subclasses of
`AbstractBehavior`.

Exports:
- `BehaviorContext`: shared runtime context passed into behaviors.
- `BehaviorExecutor`: low-level scheduler for running behaviors.
- `BehaviorEngine`: high-level engine that holds a registry and executor.
- `BehaviorAction`: helper for behavior action signals.
- `BehaviorRegistry`: named and grouped behavior storage.
"""

from .executor import BehaviorExecutor
from .context import BehaviorContext
from .actions import BehaviorAction, BehaviorActionRaw
from .behavior import AbstractBehavior
from .registry import BehaviorEntry, BehaviorRegistry
from .engine import BehaviorEngine
