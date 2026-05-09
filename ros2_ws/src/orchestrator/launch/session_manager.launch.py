from launch import LaunchDescription
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    pkg_share = get_package_share_directory('orchestrator')

    return LaunchDescription([
        Node(
            package="session_mng",
            executable="manager"
        ),
        Node(
            package="session_mng",
            executable="listener"
        )
    ])