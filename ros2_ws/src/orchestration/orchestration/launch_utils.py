from launch.actions import ExecuteProcess, LogInfo
from enum import Enum
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.some_entities_type import SomeEntitiesType

class SysEventType(Enum):
    # these must be of type uint8
    START = 0
    EXIT = 1
    CRASH = 2


def publish_process_event(proc_name: str, event_type: SysEventType, exit_code: int):
    """
    Creates action to publish a one-shot process event. 

    This is mainly used in launch.py files to bind start/exit/crash callbacks to the node's processes.
    """
    
    msg = f'\"{{proc_name: {proc_name}, event_type: {event_type.value}, exit_code: {exit_code}}}\"'
    return ExecuteProcess(
        cmd=['ros2', 'topic', 'pub', '--once', '/process_events', 'interfaces/msg/ProcessEvent', msg],
        shell=True,
        log_cmd=True,
        name=f'sysevt-{event_type.name.lower()} pub'
    )


def publish_system_status(status_code: int, note: str) -> ExecuteProcess:
    """
    Creates an action to publish a one-shot system status update. 
    
    During nominal operation, the only publisher to /system_status should be the supervisor node itself;
    therefore, this method should ever be used as a callback action for the crash of the supervisor process itself,
    in order to interrupt boot abruptly.
    """
    msg = f'\"{{status_code: {status_code}, note: {note}}}\"'
    return ExecuteProcess(
        cmd=['ros2', 'topic', 'pub', '--once', '/system_status', 'interfaces/msg/SystemStatus', msg],
        shell=True,
        name='sysstatus pub'
        )


def on_process_start(target_action, proc_name: str) -> OnProcessStart:
    """
    Event handler that publishes notification of /process_events topic on process START event.
    """
    return OnProcessStart(
            target_action=target_action,
            on_start=lambda event, _context: [
                LogInfo(msg=f"Launch-supervised process started: {event.action.name} (PID: {event.pid})"),
                
                # notify on /process_events
                publish_process_event(
                    proc_name=proc_name,
                    event_type=SysEventType.START,
                    exit_code=0 # redundant
                )
            ]
        )


def on_process_exit(target_action, proc_name: str) -> OnProcessExit:
    """
    Event handler that publishes notification of /process_events topic on process EXIT event (including errcode).
    """
    return OnProcessExit(
            target_action=target_action,
            on_exit=lambda event, _context: [
                LogInfo(msg=f"Launch-supervised process '{event.action.name}' exited with code: {event.returncode}"),

                # notify on /process_events
                publish_process_event(
                    proc_name=proc_name, 
                    event_type=SysEventType.EXIT, 
                    exit_code=event.returncode,
                )
            ]
        )


def run_on_proc_exit(target, action: SomeEntitiesType | None):
    """ Generalization for every handler of a proc exit event"""
    raise NotImplemented()