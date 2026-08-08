from system_alerts.alert import Alert, AlertActionType, Level
from orchestration.state_machine.system_fsm import SystemFSM, SystemState, SystemEvent
from orchestration.state_machine.event_mapper import map_alert_to_system_event
from system_commons import alert_codes as ac


def test_system_fsm_transitions():
    fsm = SystemFSM()

    # starting state is BOOTING
    assert fsm.state is SystemState.BOOTING

    # FATAL_FAULT forces FAULT from any state
    result = fsm.process_event(SystemEvent.FATAL_FAULT)
    assert result.changed
    assert result.new_state is SystemState.FAULT
    assert fsm.state is SystemState.FAULT

    # once in FAULT, FATAL_FAULT is noop
    result = fsm.process_event(SystemEvent.FATAL_FAULT)
    assert not result.changed
    assert result.new_state is SystemState.FAULT

    # legal transition to SHUTDOWN
    result = fsm.change_state(SystemState.SHUTDOWN)
    assert result.changed
    assert result.new_state is SystemState.SHUTDOWN


def test_system_fsm_constructed_session_flow():
    fsm = SystemFSM()
    fsm.force_change_state(SystemState.STANDBY)

    result = fsm.process_event(SystemEvent.SESSION_CREATION_REQUESTED)
    assert result.changed
    assert result.new_state is SystemState.CONNECTING

    result = fsm.process_event(SystemEvent.SESSION_CREATED)
    assert result.changed
    assert result.new_state is SystemState.ACTIVE

    result = fsm.process_event(SystemEvent.DISCONNECT_REQUESTED)
    assert result.changed
    assert result.new_state is SystemState.DISCONNECTING

    result = fsm.process_event(SystemEvent.DISCONNECTED)
    assert result.changed
    assert result.new_state is SystemState.STANDBY


def test_system_fsm_session_failure_flow():
    fsm = SystemFSM()
    fsm.force_change_state(SystemState.STANDBY)

    result = fsm.process_event(SystemEvent.SESSION_CREATION_REQUESTED)
    assert result.changed
    assert result.new_state is SystemState.CONNECTING

    result = fsm.process_event(SystemEvent.SESSION_CREATION_FAILED)
    assert result.changed
    assert result.new_state is SystemState.STANDBY


def test_event_mapper_ignores_irrelevant_alerts():
    alert = Alert(level=Level.INFO, src="session_manager", code=999, brief="OTHER")
    assert map_alert_to_system_event(AlertActionType.RAISE, alert) is None


def test_event_mapper_maps_session_alerts():
    req_alert = Alert(level=Level.INFO, src="session_manager", code=ac.INF_SESSION_CREATION_REQUEST)
    assert map_alert_to_system_event(AlertActionType.RAISE, req_alert) is SystemEvent.SESSION_CREATION_REQUESTED

    ok_alert = Alert(level=Level.INFO, src="session_manager", code=ac.INF_SESSION_CREATION_OK)
    assert map_alert_to_system_event(AlertActionType.RAISE, ok_alert) is SystemEvent.SESSION_CREATED

    failed_alert = Alert(level=Level.ERR, src="session_manager", code=ac.ERR_SESSION_CREATION_FAILED)
    assert map_alert_to_system_event(AlertActionType.RAISE, failed_alert) is SystemEvent.SESSION_CREATION_FAILED

    disconnect_alert = Alert(level=Level.INFO, src="session_manager", code=ac.INF_SESSION_CLOSURE_REQUEST)
    assert map_alert_to_system_event(AlertActionType.RAISE, disconnect_alert) is SystemEvent.DISCONNECT_REQUESTED

    disconnected_alert = Alert(level=Level.INFO, src="session_manager", code=ac.INF_SESSION_CLOSURE_OK)
    assert map_alert_to_system_event(AlertActionType.RAISE, disconnected_alert) is SystemEvent.DISCONNECTED

    fatal_alert = Alert(level=Level.FATAL, src="core", code=ac.FTL_CORE_PROC_CRASH)
    assert map_alert_to_system_event(AlertActionType.RAISE, fatal_alert) is SystemEvent.FATAL_FAULT
