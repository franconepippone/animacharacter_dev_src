from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import RegisterEventHandler
from orchestration.launch_utils import on_process_exit, on_process_start
from system_commons.proc_names import (
    SESSION_CONNECTION_SERVER, 
    SESSION_MANAGER
)

"""
This file handles configuring and launching the session managment subsystem.

Here the following entities are launched:
|-- manager (Node)
|-- connection server (Node + fastapi)

"""



def generate_launch_description():

    session_manager = Node(
        package="session_mng",
        executable="session_mng"
    )

    connection_server = Node(
        package="session_mng",
        executable="connection_listener"
    )


    return LaunchDescription([
        session_manager,
        connection_server,

        # start / exit notification handlers for session manager
        RegisterEventHandler(on_process_start(session_manager, SESSION_MANAGER)),
        RegisterEventHandler(on_process_exit(session_manager, SESSION_MANAGER)),

        # start / exit notification handlers for connection server
        RegisterEventHandler(on_process_start(connection_server, SESSION_CONNECTION_SERVER)),
        RegisterEventHandler(on_process_exit(connection_server, SESSION_CONNECTION_SERVER)),
        
    ])