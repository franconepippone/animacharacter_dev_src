from enum import Enum, auto

from .fsm import FSM



class SystemState(Enum):
    """System State of the engine"""

    BOOTING = auto()
    STANDBY = auto()
    CONNECTING = auto()
    ACTIVE = auto()
    DISCONNECTING = auto()
    FAULT = auto()
    SHUTDOWN = auto()



class SystemFSM(FSM[SystemState]):
    """
    More specilized subclass of FSM to handle the Engine system FSM.
    
    """
    def __init__(self, status_publisher) -> None:
        """Create the system FSM with initial state in BOOTING and degraded flag to False
        """
        super().__init__(SystemState.BOOTING)
        self._degraded: bool = False

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
        self._degraded = True
    
    def set_nominal(self):
        """ Clears degraded flag"""
        self._degraded = False
    