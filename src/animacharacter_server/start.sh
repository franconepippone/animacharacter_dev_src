#!/usr/bin/env bash
set -e

source /opt/ros/kilted/setup.bash
source /app/ros2_ws/install/setup.bash

MODE=${1:-all}

echo "Spinning up Animacharacter Engine [$MODE]"

# allows to choose different launch files. mode "all" is the default.
case "$MODE" in
    all)
        echo "Launching full system..."
        ros2 launch orchestration main.launch.py
        ;;

    core)
        echo "Launching core system..."
        ros2 launch orchestration core.launch.py
        ;;

    *)
        echo "Unknown mode: $MODE"
        echo "Usage: $0 [all|core]"
        exit 1
        ;;
esac