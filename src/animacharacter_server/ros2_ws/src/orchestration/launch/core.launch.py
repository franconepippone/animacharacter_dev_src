from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

"""
Here we handle the launch of the 'core' subsystem of the ros2 system. Crash of any of these processes
brings the whole system down in a fatal state, and require a full reboot. 

Here the following entities are launched:

    core.launch
        |-- hardware manager (Node)
        |-- session_manager.launch
        |   |-- manager (Node)
        |   |-- connection server (Node + fastapi)

In this file, we also bind /process_events one-shot publishers to the hwmng process enter/exit events;
The same is done for session manager in its own launch file.

As a reminder: this is done so that the supervisor node can react to system-wide process_events such as crashes
(which are fatal for processes launched in CORE), and coordinate a global graceful shutdown if possible.
"""


def generate_launch_description():
    config_file_default = PathJoinSubstitution(
        [FindPackageShare("hardware_mng"), "config", "hw_configs.yaml"]
    )

    # session manager process (process events callbacks already bound)
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
    hardware_manager_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("hardware_mng"),
                    "launch",
                    "manager.launch.py",
                ]
            )
        ),
        launch_arguments={
            "controller_config_file": LaunchConfiguration(
                "controller_config_file"
            ),
            "controller_config_name": LaunchConfiguration(
                "controller_config_name"
            ),
            "plugin_dirs": LaunchConfiguration("plugin_dirs"),
            "strict_mode": LaunchConfiguration("strict_mode"),
            'controller_operation_timeout': LaunchConfiguration(
                'controller_operation_timeout'
            ),
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "controller_config_file",
            default_value=config_file_default,
            description="YAML controller configurations file",
        ),
        DeclareLaunchArgument(
            "controller_config_name",
            default_value="",
            description="Named controller configuration; defaults from YAML",
        ),
        DeclareLaunchArgument(
            "plugin_dirs",
            default_value="",
            description="Colon-separated plugin import directories",
        ),
        DeclareLaunchArgument(
            "strict_mode",
            default_value="false",
            description="Fail node initialization if any controller plugin fails",
        ),
        DeclareLaunchArgument(
            'controller_operation_timeout',
            default_value="10.0",
            description=(
                'Seconds to wait for controller lifecycle state '
                'reconciliation and runner shutdown'
            ),
        ),
        hardware_manager_launch,

        session_manager_launch
    ])