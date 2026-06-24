from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent, ExecuteProcess, TimerAction
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
import os
from ament_index_python.packages import get_package_share_directory

from orchestration.launch_utils import publish_system_status

def generate_launch_description():
    pkg_path = get_package_share_directory('orchestration')
    
    # 1. Supervisor: Il nodo che decide lo stato
    supervisor_node = Node(
        package='orchestration',
        executable='supervisor_node',
        name='supervisor'
    )

    # 2. Watchdog Supervisor: Se il supervisor crasha, segnala e ferma tutto
    supervisor_die_handler = RegisterEventHandler(
        OnProcessExit(
            target_action=supervisor_node,
            on_exit=[
                # Pubblicazione diretta di emergenza
                publish_system_status(0, "hello"),
                TimerAction(
                    period=5, # TODO wait 5 seconds?
                    actions=[EmitEvent(event=Shutdown(reason='Supervisor Fatal Crash'))]
                ),
                
            ]
        )
    )

    # 3. Inclusioni Gerarchiche
    core_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'core.launch.py'))
    )
    
    monitor_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'monitor.launch.py'))
    )

    return LaunchDescription([
        supervisor_node,
        supervisor_die_handler,
        core_launch,
        monitor_launch
    ])