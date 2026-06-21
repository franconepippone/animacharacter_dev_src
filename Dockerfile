# syntax=docker/dockerfile:1.4

FROM ros:jazzy-ros-base

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
# Initialize rosdep (correct + idempotent)
# ---------------------------------------------------------
RUN rosdep init 2>/dev/null || true && \
    rosdep update

# ---------------------------------------------------------
# Python libs (monorepo internal)
# ---------------------------------------------------------
WORKDIR /app

# injected external context using 'docker build --build-context shared=../shared_packages'
COPY --from=shared . /tmp/libs/ 
COPY libs/ /tmp/libs/

RUN find /tmp/libs -mindepth 1 -maxdepth 1 -type d \
    -exec pip install --no-cache-dir --break-system-packages {} \; && \
    rm -rf /tmp/libs

# external python deps (pip-only ecosystem)
RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn

# ---------------------------------------------------------
# ROS2 workspace
# ---------------------------------------------------------
ENV ROS_WS=/opt/ros2_ws
WORKDIR ${ROS_WS}

COPY ros2_ws/src ./src

SHELL ["/bin/bash", "-c"]

# IMPORTANT: source ROS before rosdep
RUN source /opt/ros/jazzy/setup.bash 
RUN apt-get update
RUN rosdep update && \ 
    rosdep install \
        --from-paths src \
        --ignore-src \
        --skip-keys="rosidl_generator_mypy" \
        -r -y

# build
RUN source /opt/ros/jazzy/setup.bash && \
    colcon build --symlink-install

# ---------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------
ENV PLUGIN_DIRS=/plugins:/app/plugins_builtin
ENV CONFIG_FILE=/config/config.yaml
ENV INPUT_CONFIG=""
ENV STRICT_MODE="true"

RUN mkdir -p /app/plugins_builtin /plugins /config

RUN echo "source /opt/ros/jazzy/setup.bash" >> /etc/bash.bashrc && \
    echo "source ${ROS_WS}/install/setup.bash" >> /etc/bash.bashrc

CMD ["bash"]