from __future__ import annotations

from enum import Enum, auto

from .fsm import FSM, StateChangeResult
from .event_mapper import SystemEvent

class SystemState(Enum):
    """Externally visible system states."""

    BOOTING = auto()
    STANDBY = auto()
    CONNECTING = auto()
    ACTIVE = auto()
    DISCONNECTING = auto()
    FAULT = auto()
    SHUTDOWN = auto()


class SystemFSM(FSM[SystemState]):
    """A system state projection based on semantic system events.

    The FSM does not own alerts, timers, publishers, or loggers.
    It only maps current state and semantic event to the next visible state.
    """

    def __init__(self) -> None:
        super().__init__(SystemState.BOOTING)

        self.add_transitions(SystemState.BOOTING, {
            SystemState.STANDBY,
            SystemState.FAULT,
        })

        self.add_transitions(SystemState.STANDBY, {
            SystemState.CONNECTING,
            SystemState.FAULT,
        })

        self.add_transitions(SystemState.CONNECTING, {
            SystemState.STANDBY,
            SystemState.ACTIVE,
            SystemState.FAULT,
        })

        self.add_transitions(SystemState.ACTIVE, {
            SystemState.DISCONNECTING,
            SystemState.FAULT,
        })

        self.add_transitions(SystemState.DISCONNECTING, {
            SystemState.STANDBY,
            SystemState.FAULT,
        })

        self.add_transitions(SystemState.FAULT, {
            SystemState.SHUTDOWN,
        })

    def process_event(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        if event is SystemEvent.FATAL_FAULT:
            if self.state is SystemState.FAULT:
                return self._noop()
            return self.force_change_state(SystemState.FAULT)

        if self.state is SystemState.BOOTING:
            return self._handle_booting(event)

        if self.state is SystemState.STANDBY:
            return self._handle_standby(event)

        if self.state is SystemState.CONNECTING:
            return self._handle_connecting(event)

        if self.state is SystemState.ACTIVE:
            return self._handle_active(event)

        if self.state is SystemState.DISCONNECTING:
            return self._handle_disconnecting(event)

        return self._noop()

    def _handle_booting(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        return self._noop()

    def _handle_standby(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        if event is SystemEvent.SESSION_CREATION_REQUESTED:
            return self.change_state(SystemState.CONNECTING)
        return self._noop()

    def _handle_connecting(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        if event is SystemEvent.SESSION_CREATED:
            return self.change_state(SystemState.ACTIVE)
        if event is SystemEvent.SESSION_CREATION_FAILED:
            return self.change_state(SystemState.STANDBY)
        return self._noop()

    def _handle_active(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        if event is SystemEvent.DISCONNECT_REQUESTED:
            return self.change_state(SystemState.DISCONNECTING)
        if event is SystemEvent.DISCONNECTED:
            return self.force_change_state(SystemState.STANDBY)
        return self._noop()

    def _handle_disconnecting(self, event: SystemEvent) -> StateChangeResult[SystemState]:
        if event is SystemEvent.DISCONNECTED:
            return self.change_state(SystemState.STANDBY)
        return self._noop()

    def _noop(self) -> StateChangeResult[SystemState]:
        print("no operation occurred")
        return StateChangeResult(self.state, self.state, True)
