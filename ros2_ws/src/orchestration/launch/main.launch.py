import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent, ExecuteProcess, TimerAction
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

from orchestration.launch_utils import publish_system_status

"""
This is the primary entrypoint to the ros2 application. In here, all processes are configured and launched.

This is the full launch graph, in launch order:

main.launch
    |-- Supervisor (Node)
    |-- diagnostics.launch (Node)
    |-- core.launch
    |   |-- hardware manager (Node)
    |   |-- session_manager.launch
    |   |   |-- manager (Node)
    |   |   |-- connection server (Node + fastapi)
    |-- monitor.launch
    |   |-- webUI (Node)
    |   |-- status panel (Node)
    |   |-- (other...)
    |-- (other...)

Here we launch the Supervisor Node, and all the other subsystems.


"""



def generate_launch_description():
    pkg_path = get_package_share_directory('orchestration')
    
    # 1. Supervisor: Il nodo che decide lo stato
    supervisor_node = Node(
        package='orchestration',
        executable='supervisor_node',
        name='supervisor'
    )

    # Supervisor watchdog: if supervisor crashes, we shutdown everything 
    supervisor_die_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=supervisor_node,
            on_exit=[
                # Pubblicazione diretta di emergenza
                publish_system_status(0, "hello"),
                TimerAction(
                    period=2, # TODO wait 5 seconds?
                    actions=[EmitEvent(event=Shutdown(reason='Supervisor Fatal Crash'))]
                ),
                
            ]
        )
    )

    
    # ==================
    # launch all other subsystems

    # core (session manager + hardware manager)
    core_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'core.launch.py'))
    )
    
    # monitor (webUI + control panel)
    monitor_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'monitor.launch.py'))
    )

    dagnostics_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'diagnostics.launch.py'))
    )

    return LaunchDescription([
        supervisor_node,
        dagnostics_launch,
        core_launch,
        monitor_launch,
        
        supervisor_die_handler,
    ])