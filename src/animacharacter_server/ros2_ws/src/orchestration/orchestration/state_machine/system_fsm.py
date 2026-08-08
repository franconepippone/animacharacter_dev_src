from typing import Callable, Protocol
from enum import Enum, auto
from dataclasses import dataclass
from rclpy.publisher import Publisher
from interfaces.msg import SystemStatus

from .fsm import FSM

from system_alerts.system_alerts import SysAlertsServer, Alert
from system_alerts.system_alerts.alert import AlertActionType, Level
from system_commons import alert_codes as acd


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


@dataclass(slots=True, frozen=True)
class StateChangeResult:
    """Result of a state change in the system FSM."""
    prev_state: SystemState
    new_state: SystemState
    legal_transition: bool

    @property
    def changed(self) -> bool:
        """Returns True if the state has changed, False otherwise."""
        return self.prev_state != self.new_state


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
    
    
    def _update_booting(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def _update_standby(self, action: AlertActionType, alert: Alert) -> bool:
        if action == AlertActionType.RAISE:
            if alert.code == acd.INF_SESSION_CREATION_REQUEST:
                legal = self.force_change_state(SystemState.CONNECTING)
                return legal

        # log if we reach here
        return False
    
    def _update_connecting(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def _update_active(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def _update_disconnecting(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def _update_fault(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def _update_shutdown(self, action: AlertActionType, alert: Alert) -> bool:
        ...

    def update_state(self, action: AlertActionType, alert: Alert) -> StateChangeResult:
        """Utility method for updating the state directly from alert changes"""

        prev_state = self.state 

        # handle degraded flag
        if len(self.alert_server.get_active_alerts()) > 0:
            self.set_degraded()
        else:
            self.set_nominal()

        # handle fatal alerts
        if len(self.alert_server.get_alerts_from_level(Level.FATAL)) > 0:
            legal = self.force_change_state(SystemState.FAULT)
            self.fault_ref_alert = alert
            return StateChangeResult(prev_state, self.state, legal)

        if self.state == SystemState.BOOTING:
            legal = self._update_booting(action, alert)
        elif self.state == SystemState.STANDBY:
            legal = self._update_standby(action, alert)
        elif self.state == SystemState.CONNECTING:
            legal = self._update_connecting(action, alert)
        elif self.state == SystemState.ACTIVE:
            legal = self._update_active(action, alert)
        elif self.state == SystemState.DISCONNECTING:
            legal = self._update_disconnecting(action, alert)
        elif self.state == SystemState.FAULT:
            legal = self._update_fault(action, alert)
        elif self.state == SystemState.SHUTDOWN:
            legal = self._update_shutdown(action, alert)
        else:
            raise ValueError(f"Unknown system state: {self.state}")

        return StateChangeResult(prev_state, self.state, legal)