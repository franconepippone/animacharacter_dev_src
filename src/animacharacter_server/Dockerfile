# syntax=docker/dockerfile:1.4

FROM ros:kilted-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------
# Base system deps (IMPORTANT: include rosdep here)
# ---------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-rosdep \
    python3-argcomplete \
    python3-colcon-common-extensions \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Initialize rosdep
# ---------------------------------------------------------
RUN rosdep init 2>/dev/null || true && \
    rosdep update

# ---------------------------------------------------------
# Python dependencies setup (global)
# ---------------------------------------------------------
WORKDIR /app

# injected external context using 'docker build --build-context shared=../shared_packages'
COPY --from=shared . /tmp/libs/ 
COPY libs/ /tmp/libs/

# install all internal packages
RUN find /tmp/libs -mindepth 1 -maxdepth 1 -type d \
    -exec pip install --no-cache-dir --break-system-packages {} \; && \
    rm -rf /tmp/libs

# external python deps
RUN pip install --no-cache-dir --break-system-packages --ignore-installed \
    fastapi==0.128.0 \
    uvicorn==0.40.0

# ---------------------------------------------------------
# ROS2 workspace
# ---------------------------------------------------------
ENV ROS_WS=/app/ros2_ws
WORKDIR ${ROS_WS}

COPY ros2_ws/src ./src

SHELL ["/bin/bash", "-c"]

# IMPORTANT: source ROS before rosdep
RUN source /opt/ros/kilted/setup.bash 
RUN apt-get update
RUN rosdep update && \ 
    rosdep install \
        --from-paths src \
        --ignore-src \
        --skip-keys="rosidl_generator_mypy" \
        -r -y

# build
RUN source /opt/ros/kilted/setup.bash && \
    colcon build --symlink-install


# Adding engine start shortcut command
COPY start.sh /usr/local/bin/start
RUN chmod +x /usr/local/bin/start

# ---------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------
ENV CONTROLLER_BUILTIN_PLUGINS_DIR=/app/ros2_ws/src/hardware_mng/hardware_mng/builtin_plugins

# register both builtin plugins dir and folder reserved to user plugins (can be mounted)
# Other user specified folders where hardware plugins will be searcehd can be added here
ENV CONTROLLERS_PLUGIN_DIRS=/app/plugins/hardware_controllers:${CONTROLLER_BUILTIN_PLUGINS_DIR}

# List of possible configuration files. The last one found in the list will be used.
ENV CONTROLLERS_CONFIG_FILES=${BUILTIN_PLUGINS_DIR}/hw_configs.yaml:/app/plugins/hardware_controllers/hw_configs.yaml
ENV HWM_INPUT_CONFIG=""
ENV HWM_STRICT_MODE="true"

# Users who want to add plugins can mount this directory and place them there directly
RUN mkdir -p /app/plugins/hardware_controllers

RUN echo "source /opt/ros/kilted/setup.bash" >> /etc/bash.bashrc && \
    echo "source ${ROS_WS}/install/setup.bash" >> /etc/bash.bashrc

CMD ["bash"]