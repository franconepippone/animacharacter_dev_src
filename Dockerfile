# ROS 2 Jazzy – Raspberry Pi (ARM64) Deployment Image
FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# Install build + runtime dependencies
RUN apt update && apt install -y \
    python3-pip \
    python3-argcomplete \
    python3-colcon-common-extensions \
    ros-jazzy-ament-cmake \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*


# Install local Python libraries into system Python
# (ROS Python uses system site-packages)
WORKDIR /app
COPY libs libs
RUN pip install --no-cache-dir --break-system-packages ./libs/pySerialDevice

# ROS 2 workspace
ENV ROS_WS=/opt/ros2_ws
WORKDIR ${ROS_WS}

COPY ros2_ws/src ./src

# Build workspace
SHELL ["/bin/bash", "-c"]

RUN source /opt/ros/jazzy/setup.bash && \
    colcon build --symlink-install

# Auto-source ROS + workspace for runtime shells
RUN echo "source /opt/ros/jazzy/setup.bash" >> /etc/bash.bashrc && \
    echo "source ${ROS_WS}/install/setup.bash" >> /etc/bash.bashrc

# ---------------------------------------------------------
# Default command (override in docker-compose if needed)
# ---------------------------------------------------------
CMD ["bash"]
