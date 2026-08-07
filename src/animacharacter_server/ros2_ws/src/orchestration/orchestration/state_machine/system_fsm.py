from typing import Callable, Protocol
from enum import Enum, auto
from rclpy.publisher import Publisher
from interfaces.msg import SystemStatus

from .fsm import FSM

from system_alerts.system_alerts import SysAlertsServer, Alert
from system_alerts.system_alerts.alert import AlertActionType
from system_alerts.system_alerts import alerts_def as alerts


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


class SystemFSM(FSM[SystemState]):
    """
    More specilized subclass of FSM to handle the Engine system FSM.
    
    """
    def __init__(self, publish_status_cb: StatusPublisher, alert_server: SysAlertsServer) -> None:
        """Create the system FSM with initial state in BOOTING and degraded flag to False
        """
        super().__init__(SystemState.BOOTING)
        self._degraded: bool = False
        self.publish_status_cb = publish_status_cb
        self.alert_server = alert_server

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
    
    
    def _update_booting(self, action: AlertActionType, alert: Alert):
        ...

    def _update_standby(self, action: AlertActionType, alert: Alert):
        if action == AlertActionType.RAISE:
            if alert.code == alerts.INF_SESSION_CREATION_REQUEST:
                self.change_state(SystemState.CONNECTING)
                return

        # log if we reach here

    def _update_connecting(self, action: AlertActionType, alert: Alert):
        ...

    def _update_active(self, action: AlertActionType, alert: Alert):
        ...

    def _update_disconnecting(self, action: AlertActionType, alert: Alert):
        ...

    def _update_fault(self, action: AlertActionType, alert: Alert):
        ...

    def _update_shutdown(self, action: AlertActionType, alert: Alert):
        ...

    def update_state(self, action: AlertActionType, alert: Alert):
        """Utility method for updating the state directly from alert changes"""
        
        if len(self.alert_server.get_active_alerts()) > 0:
            self.set_degraded()
        else:
            self.set_nominal()

        if self.state == SystemState.BOOTING:
            self._update_booting(action, alert)
        elif self.state == SystemState.STANDBY:
            self._update_standby(action, alert)
        elif self.state == SystemState.CONNECTING:
            self._update_connecting(action, alert)
        elif self.state == SystemState.ACTIVE:
            self._update_active(action, alert)
        elif self.state == SystemState.DISCONNECTING:
            self._update_disconnecting(action, alert)
        elif self.state == SystemState.FAULT:
            self._update_fault(action, alert)
        elif self.state == SystemState.SHUTDOWN:
            self._update_shutdown(action, alert)
