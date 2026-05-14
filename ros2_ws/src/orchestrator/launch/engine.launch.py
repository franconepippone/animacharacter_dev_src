from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import ThisLaunchFileDir

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    session_management = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("session_mng"),
                "launch",
                "main.launch.py"
            ])
        ),
        launch_arguments=None
    )
    
    hardware_mng = Node(
        package='hardware_mng',
        executable='main',
        output="screen"
    )

    hardware_mng_supervisor = Node(
            package="orchestrator",
            executable="lifecycle_supervisor",
            name="hardware_mng_lifecycle_supervisor",
            parameters=[{
                "target_node": "/hardware_manager"
            }],
            output="screen"
        )

    return LaunchDescription([
        session_management,
        hardware_mng,
        hardware_mng_supervisor
    ])
