from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

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