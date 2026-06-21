#!/usr/bin/env bash
set -e

echo "Spinning up Animacharacter Engine..."

source /opt/ros/jazzy/setup.bash
source /app/ros2_ws/install/setup.bash

ros2 launch orchestrator engine.launch.py