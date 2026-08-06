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
monitor.launch
|-- webUI (Node)
|-- status panel (Node)
|-- (other...)

"""



def generate_launch_description():


    return LaunchDescription()