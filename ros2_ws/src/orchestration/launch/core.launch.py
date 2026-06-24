from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent, LogInfo
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from orchestration.launch_utils import publish_system_event, SysEventType
from orchestration.proc_names import SESSION_MANAGER

"""
Here we handle the launch of the 'core' subsystem of the ros2 system. Crash of any of these processes
brings the whole system down in a fatal state, and require a full reboot. 

Here the following entities are launched:

    core.launch
        |-- hardware manager (Node)
        |-- session_manager.launch
        |   |-- manager (Node)
        |   |-- connection server (Node + fastapi)

In this file, we also bind /system_event one-shot publishers to the hwmng process enter/exit events;
The same is done for session manager in its own launch file.

As a reminder: this is done so that the supervisor node can react to system-wide system_events such as crashes
(which are fatal for processes launched in CORE), and coordinate a global graceful shutdown if possible.
"""


def generate_launch_description():
    
    # session manager process (process events callbacks already bound)
    session_manager = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("session_mng"),
                "launch",
                "session_manager.launch.py"
            ])
        ),
        launch_arguments=None
    )
    
    hardware_manager = Node(
        package='hardware_mng',
        executable='hardware_mng',
        output="screen" # TODO what is this?
    )



    # Notification of hardware_manager exit to /system_events
    hw_die_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=hardware_manager,
            on_exit=lambda event, _context: [
                LogInfo(msg=f"Process {event.action.name} exited with code: {event.returncode}"),

                # notify on /system_events
                publish_system_event(
                    proc_name=HARDWARE_MANAGER, 
                    event_type=SysEventType.EXIT, 
                    exit_code=event.returncode,
                )
            ]
        )
    )

    # Notification of hardware_manager start to /system_events
    hw_start_handler = RegisterEventHandler(
        OnProcessStart(
            target_action=hardware_manager,
            on_start=lambda event, _context: [
            LogInfo(msg=f"Process started: {event.action.name} (PID: {event.pid})"),
            
            # notify on /system_events
            publish_system_event(
                proc_name=HARDWARE_MANAGER,
                event_type=SysEventType.START,
                exit_code=0 # redundant
            )
        ]
        )
    )

    return LaunchDescription([
        hardware_manager,
        hw_die_handler,
        hw_start_handler,
        
        session_manager
    ])
