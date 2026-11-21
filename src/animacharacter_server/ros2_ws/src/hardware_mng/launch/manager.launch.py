from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import yaml
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from orchestration.launch_utils import on_process_exit, on_process_start
from system_commons.proc_names import HARDWARE_MANAGER


def _launch_manager(context: Any) -> list[Any]:
    config_path = LaunchConfiguration("controller_config_file").perform(context)
    config_name = LaunchConfiguration("controller_config_name").perform(context)
    plugin_dirs_arg = LaunchConfiguration("plugin_dirs").perform(context)
    strict_mode_arg = LaunchConfiguration("strict_mode").perform(context).lower()
    shutdown_timeout = float(
        LaunchConfiguration("controller_shutdown_timeout").perform(context)
    )

    if strict_mode_arg not in {"true", "false"}:
        raise ValueError("strict_mode must be 'true' or 'false'")
    if shutdown_timeout < 0:
        raise ValueError("controller_shutdown_timeout cannot be negative")

    with open(config_path, encoding="utf-8") as config_file:
        config: Any = yaml.safe_load(config_file)
    if not isinstance(config, Mapping):
        raise ValueError(f"Controller config '{config_path}' must be a mapping")

    selected_config = config_name or config.get("default_config")
    if not isinstance(selected_config, str) or not selected_config:
        raise ValueError(
            "controller_config_name must be set or config must define "
            "a string 'default_config'"
        )

    controller_paths = config.get(selected_config)
    if not isinstance(controller_paths, list) or not all(
        isinstance(path, str) and path for path in controller_paths
    ):
        raise ValueError(
            f"Configuration '{selected_config}' must be a list of controller paths"
        )

    plugin_dirs = [
        path.strip()
        for path in plugin_dirs_arg.split(os.pathsep)
        if path.strip()
    ]
    hardware_manager = Node(
        package="hardware_mng",
        executable="hardware_mng",
        name="hardware_manager",
        output="screen",
        parameters=[
            {
                "controller_paths": controller_paths,
                "plugin_dirs": plugin_dirs,
                "strict_mode": strict_mode_arg == "true",
                "controller_shutdown_timeout": shutdown_timeout,
            }
        ],
    )
    return [
        hardware_manager,
        RegisterEventHandler(on_process_start(hardware_manager, HARDWARE_MANAGER)),
        RegisterEventHandler(on_process_exit(hardware_manager, HARDWARE_MANAGER)),
    ]


def generate_launch_description() -> LaunchDescription:
    config_file_default = PathJoinSubstitution(
        [FindPackageShare("hardware_mng"), "config", "hw_configs.yaml"]
    )
    return LaunchDescription(
        [
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
                "controller_shutdown_timeout",
                default_value="10.0",
                description="Seconds to wait for controller runner threads to stop",
            ),
            OpaqueFunction(function=_launch_manager),
        ]
    )