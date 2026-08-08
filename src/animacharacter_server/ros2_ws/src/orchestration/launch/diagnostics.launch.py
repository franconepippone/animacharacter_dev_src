from launch import LaunchDescription
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory
import os

"""
This launch file simply starts the diagnostics_aggregator node
"""


def generate_launch_description():

    pkg_share = get_package_share_directory('orchestration')

    config_file = os.path.join(pkg_share, 'config', 'diagnostics.yaml')
    return LaunchDescription([])
    return LaunchDescription([
        Node(
            package="diagnostic_aggregator",
            executable="aggregator_node",
            name="diagnostic_aggregator",
            parameters=[config_file]
        )
    ])