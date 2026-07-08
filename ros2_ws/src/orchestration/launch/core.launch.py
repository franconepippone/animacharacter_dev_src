from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent, LogInfo
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from orchestration.launch_utils import on_process_exit, on_process_start, SysEventType
from orchestration.proc_names import HARDWARE_MANAGER

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
    
    # session manager process (process system events callbacks already bound)
    session_manager_launch = IncludeLaunchDescription(
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

    return LaunchDescription([
        hardware_manager,
        RegisterEventHandler(on_process_start(hardware_manager, HARDWARE_MANAGER)),
        RegisterEventHandler(on_process_exit(hardware_manager, HARDWARE_MANAGER)),

        session_manager_launch
    ])