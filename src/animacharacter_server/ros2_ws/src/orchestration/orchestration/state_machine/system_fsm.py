from typing import Callable, Protocol
from enum import Enum, auto

from .fsm import FSM

from rclpy.publisher import Publisher
from interfaces.msg import SystemStatus

from system_alerts.system_alerts import SysAlertsServer, Alert

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
    def __init__(self, publish_status_cb: StatusPublisher) -> None:
        """Create the system FSM with initial state in BOOTING and degraded flag to False
        """
        super().__init__(SystemState.BOOTING)
        self._degraded: bool = False
        self.publish_status_cb = publish_status_cb

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
                SystemState.ACTIVE
            })
        
        self.add_transitions(SystemState.ACTIVE, {
                SystemState.DISCONNECTING,
                SystemState.FAULT
            })
        
        self.add_transitions(SystemState.DISCONNECTING, {
                SystemState.STANDBY
            })
        
        self.add_transitions(SystemState.FAULT, {
                SystemState.SHUTDOWN
            })
        
        # no transition for SHUTDOWN, state is final

    
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
    
    def _update_booting(self, ser: SysAlertsServer):
        ...
    
    def update_state(self, alert_server: SysAlertsServer):
        """Utility method for updating the state directly by reading the currently active alerts"""
        
        if len(alert_server.get_active_alerts()) > 0:
            self.set_degraded()
        else:
            self.set_nominal()

        if alert_server.is_alert_active(2):
            # alert 2 is active, drive fsm
