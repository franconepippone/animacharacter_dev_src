from launch.actions import ExecuteProcess, LogInfo
from enum import Enum
from launch.event_handlers import OnProcessExit, OnProcessStart

class SysEventType(Enum):
    # these must be of type uint8
    START = 0
    EXIT = 1
    CRASH = 2


def publish_system_event(proc_name: str, event_type: SysEventType, exit_code: int):
    """
    Creates action to publish a one-shot system event. 

    This is mainly used in launch.py files to bind start/exit/crash callbacks to the node's processes.
    """
    
    msg = f"{{node_name: {proc_name}, event_type: {event_type}, exit_code: {exit_code}}}"
    return ExecuteProcess(
        cmd=['ros2', 'topic', 'pub', '--once', '/system_events', 'interfaces/msg/SystemEvent', msg],
        shell=True
    )


def publish_system_status(status_code: int, note: str) -> ExecuteProcess:
    """
    Creates an action to publish a one-shot system status update. 
    
    During nominal operation, the only publisher to /system_status should be the supervisor node itself;
    therefore, this method should ever be used as a callback action for the crash of the supervisor process itself,
    in order to interrupt boot abruptly.
    """
    return ExecuteProcess(cmd=[
        'ros2', 'topic', 'pub', '--once', '/system_status', 'interfaces/msg/SystemStatus', 
        f'*{{status_code: {status_code}, note: {note}}}']
        )


def on_process_start(target_action, proc_name: str) -> OnProcessStart:
    """
    Event handler that publishes notification of /system_events topic on process START event.
    """
    return OnProcessStart(
            target_action=target_action,
            on_start=lambda event, _context: [
                LogInfo(msg=f"Process started: {event.action.name} (PID: {event.pid})"),
                
                # notify on /system_events
                publish_system_event(
                    proc_name=proc_name,
                    event_type=SysEventType.START,
                    exit_code=0 # redundant
                )
            ]
        )


def on_process_exit(target_action, proc_name: str) -> OnProcessExit:
    """
    Event handler that publishes notification of /system_events topic on process EXIT event (including errcode).
    """
    return OnProcessExit(
            target_action=target_action,
            on_exit=lambda event, _context: [
                LogInfo(msg=f"Process {event.action.name} exited with code: {event.returncode}"),

                # notify on /system_events
                publish_system_event(
                    proc_name=proc_name, 
                    event_type=SysEventType.EXIT, 
                    exit_code=event.returncode,
                )
            ]
        )