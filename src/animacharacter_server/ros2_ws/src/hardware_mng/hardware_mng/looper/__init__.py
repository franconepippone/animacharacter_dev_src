"""Deprecated threaded loop implementation retained for compatibility."""

import warnings

warnings.warn(
    "hardware_mng.looper is deprecated; use lifecycle_pkg runners instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .looper_util import LoopSupervisor, LoopDescriptor, LoopRequest, LoopAction, Signal

LoopActionRequest = LoopRequest

__all__ = [
    "LoopSupervisor",
    "LoopDescriptor",
    "LoopRequest",
    "LoopActionRequest",
    "LoopAction",
    "Signal",
]
from .display_ascii import display_status_from_json