from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Level:
    INFO = 0
    WARN = 1
    ERR = 2
    FATAL = 3


class AlertActionType(str, Enum):
    """Either "raise" or "clear" an alert."""

    RAISE = "raise"
    CLEAR = "clear"


@dataclass(frozen=True, slots=True)
class Alert:
    """Simple Python representation of a system alert.

    This dataclass is the application-level payload used by clients and the
    server. It is converted to and from the ROS message type when crossing the
    IPC boundary.
    """
    level: int
    src: str
    code: int
    ttl: float = math.inf
    subcode: int = -1
    brief: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "src": self.src,
            "code": self.code,
            "ttl": self.ttl,
            "subcode": self.subcode,
            "brief": self.brief,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Alert":
        def _coerce_int(key: str, default: int) -> int:
            value = payload.get(key, default)
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(value)
            return default

        def _coerce_float(key: str, default: float) -> float:
            value = payload.get(key, default)
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value)
            return default

        return cls(
            level=_coerce_int("level", Level.INFO),
            src=str(payload.get("src", "")),
            code=_coerce_int("code", -1),
            ttl=_coerce_float("ttl", math.inf),
            subcode=_coerce_int("subcode", -1),
            brief=str(payload.get("brief", "")),
            description=str(payload.get("description", "")),
        )


def empty_alert() -> Alert:
    """Return a default empty alert."""
    return Alert(
        level=Level.INFO,
        src="",
        code=-1,
        ttl=math.inf,
        subcode=-1,
        brief="",
        description="",
    )