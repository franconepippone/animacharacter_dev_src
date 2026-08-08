from typing import Callable, Protocol
from enum import Enum, auto
from dataclasses import dataclass
from rclpy.publisher import Publisher
from interfaces.msg import SystemStatus

from .fsm import FSM, StateChangeResult

from system_alerts import SysAlertsServer, Alert
from system_alerts.alert import AlertActionType, Level
from system_commons import alert_codes as acd

from dataclasses import dataclass

class SystemState(Enum):
    """System State of the engine"""

    BOOTING = auto()
    STANDBY = auto()
    CONNECTING = auto()
    ACTIVE = auto()
    DISCONNECTING = auto()
    FAULT = auto()
    SHUTDOWN = auto()



class StatusPublisher(Protocol):
    """Template for a callable that creates and publishes a system status message."""
    def __call__(self, 
            state_id: SystemState, 
            is_degraded: bool,
            fault_alert: Alert,
            ) -> None:
        ...


class UnhandledAlertWarning(Exception):
    """Raised inside an update function when an alert coming from an unexpected source is received"""
    def __init__(self, action: AlertActionType, alert: Alert, current_state: SystemState, note: str, *args: object):
        super().__init__(*args)
        self.note = note
        self.state = current_state


class SystemFSM(FSM[SystemState]):
    """
    More specilized subclass of FSM to handle the Engine system FSM.
    
    """
    def __init__(self, alert_server: SysAlertsServer) -> None:
        """Create the system FSM with initial state in BOOTING and degraded flag to False
        """
        super().__init__(SystemState.BOOTING)
        self._degraded: bool = False
        self.alert_server = alert_server
        self.fault_ref_alert: Alert | None = None

        # state machine according to description in docs/system_status.md

        self.add_transitions(SystemState.BOOTING, {
                SystemState.STANDBY,
                SystemState.FAULT
            })
        
        self.add_transitions(SystemState.STANDBY, {
                SystemState.CONNECTING,
                SystemState.FAULT
            })

        self.add_transitions(SystemState.CONNECTING, {
                SystemState.STANDBY,
                SystemState.ACTIVE,
                SystemState.FAULT
            })
        
        self.add_transitions(SystemState.ACTIVE, {
                SystemState.DISCONNECTING,
                SystemState.FAULT
            })
        
        self.add_transitions(SystemState.DISCONNECTING, {
                SystemState.STANDBY,
                SystemState.FAULT
            })
        
        self.add_transitions(SystemState.FAULT, {
                SystemState.SHUTDOWN
            })

    @property
    def degraded(self) -> bool:
        return self._degraded
    
    def set_degraded(self):
        """ Sets degraded flag"""
        if not self._degraded:
            self._degraded = True

    def set_nominal(self):
        """ Clears degraded flag"""
        self._degraded = False


    ### ============================
    ### STATE UPDATE LOGIC
    ### ============================
    

    def _update_standby(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        if action == AlertActionType.RAISE:
            if alert.code == acd.INF_SESSION_CREATION_REQUEST:
                return self.force_change_state(SystemState.CONNECTING)

        raise UnhandledAlertWarning(action, alert, self.state, "The alert was left unhandled by the fsm update logic")
    
    def _update_connecting(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        if action == AlertActionType.RAISE:
            if alert.code == acd.INF_SESSION_CREATION_OK:
                return self.force_change_state(SystemState.ACTIVE)
            elif alert.code == acd.ERR_SESSION_CREATION_FAILED:
                return self.force_change_state(SystemState.STANDBY)

        raise UnhandledAlertWarning(action, alert, self.state, "The alert was left unhandled by the fsm update logic")

    def _update_active(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        ...

    def _update_disconnecting(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        ...

    def _update_fault(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        ...

    def _update_shutdown(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        ...

    def update_state(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        """Utility method for updating the state directly from alert changes"""

        # handle degraded flag
        if len(self.alert_server.get_active_alerts()) > 0:
            self.set_degraded()
        else:
            self.set_nominal()

        # handle fatal alerts
        if len(self.alert_server.get_alerts_from_level(Level.FATAL)) > 0:
            result = self.force_change_state(SystemState.FAULT)
            self.fault_ref_alert = alert
            return result

        if self.state == SystemState.BOOTING:
            raise ValueError("State machine cannot automatically transition away from booting")
        elif self.state == SystemState.STANDBY:
            return self._update_standby(action, alert)
        elif self.state == SystemState.CONNECTING:
            return self._update_connecting(action, alert)
        elif self.state == SystemState.ACTIVE:
            return self._update_active(action, alert)
        elif self.state == SystemState.DISCONNECTING:
            return self._update_disconnecting(action, alert)
        elif self.state == SystemState.FAULT:
            return self._update_fault(action, alert)
        elif self.state == SystemState.SHUTDOWN:
            return self._update_shutdown(action, alert)
        else:
            raise ValueError(f"Unknown system state: {self.state}")