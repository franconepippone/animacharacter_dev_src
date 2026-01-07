# ROS 2 Jazzy base (Ubuntu 24.04)
FROM ros:jazzy-ros-base

# Install useful dev tools
RUN apt update && apt install -y \
    python3-colcon-common-extensions \
    python3-argcomplete \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app
# Copy and install required python libraries
COPY libs libs

RUN pip install --break-system-packages libs/pySerialDevice 


# Workspace location
ENV ROS_WS=ros2_ws
WORKDIR $ROS_WS
COPY ros2_ws/src src


# Auto-source ROS environment
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc


# Build and source workspace
RUN colcon build

# Auto-source workspace for interactive shells
RUN echo "source install/setup.bash" >> /root/.bashrc

# Default to interactive shell
CMD ["bash"]
