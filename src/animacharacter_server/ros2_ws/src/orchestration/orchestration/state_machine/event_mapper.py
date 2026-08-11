from __future__ import annotations

from system_alerts.alert import Alert, AlertActionType, Level
from system_commons import alert_codes as ac
from enum import Enum, auto

class SystemEvent(Enum):
    """Semantic system events consumed by the SystemFSM."""

    SESSION_CREATION_REQUESTED = auto()
    SESSION_CREATED = auto()
    SESSION_CREATION_FAILED = auto()
    DISCONNECT_REQUESTED = auto()
    DISCONNECTED = auto()
    FATAL_FAULT = auto()

def map_alert_to_system_event(action: AlertActionType, alert: Alert) -> SystemEvent | None:
    """Translate raw alert lifecycle changes into semantic system events."""

    if action is AlertActionType.RAISE:
        if alert.level == Level.FATAL:
            return SystemEvent.FATAL_FAULT
        
        if alert.code == ac.INF_SESSION_CREATION_REQUEST:
            return SystemEvent.SESSION_CREATION_REQUESTED

        if alert.code == ac.INF_SESSION_CREATION_OK:
            return SystemEvent.SESSION_CREATED

        if alert.code == ac.ERR_SESSION_CREATION_FAILED:
            return SystemEvent.SESSION_CREATION_FAILED

        if alert.code == ac.INF_SESSION_CLOSURE_REQUEST:
            return SystemEvent.DISCONNECT_REQUESTED

        if alert.code == ac.INF_SESSION_CLOSURE_OK:
            return SystemEvent.DISCONNECTED

    return None
