import threading
from typing import TYPE_CHECKING, cast, Any
from pydantic import BaseModel
from dataclasses import dataclass

import rclpy
from rclpy.logging import get_logger
from rclpy.node import Node
from interfaces.srv import CreateSession  # replace with your service type
from rclpy.executors import SingleThreadedExecutor


if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse

SERVICE_NAME = "create_session"


class SessionCreationHttpResponse(BaseModel):
    success: bool
    msg: str = ""
    nng_port: int = -1
    udp_port: int = -1
    udp_secret_key: str = ""
    token: str = ""

@dataclass
class RequestArguments:
    ip: str
    udp_port: int
    meta: Any = None

class RosServiceNode(Node):
    def __init__(self):
        super().__init__('session_request_listener')
        self.cli = self.create_client(CreateSession, SERVICE_NAME)

    def make_session_creation_request(self, args: RequestArguments, timeout_sec: float = 5) -> SessionCreationHttpResponse: 
        """
        Create a session by making a ROS2 service call to the session manager node.
        This method sends a CreateSession request to the ROS2 service and waits
        for the response to complete before returning.
        Returns:
            SessionCreationHttpResponse: A pydantic model response ready to be sent back to the http client.
        """
        if not self.cli.service_is_ready():
            self.get_logger().warning('A request to create a session has been made, but service was not ready yet.')
            return SessionCreationHttpResponse(success=False)
        
        # build request
        request = CreateSession.Request()
        request.client_ip = args.ip
        request.client_udp_port = args.udp_port

        future = self.cli.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_sec)
        result = future.result()
        
        if result is None:
            return SessionCreationHttpResponse(success=False)

        typed_result: CreateSessionResponse = result
        
        return SessionCreationHttpResponse(
            success=typed_result.success,
            msg=typed_result.msg,
            nng_port=typed_result.tcp_port,
            udp_port=typed_result.udp_port,
            udp_secret_key=typed_result.session_secret,
            token=typed_result.session_secret
        )


ros_node: RosServiceNode | None = None

def get_node() -> RosServiceNode:
    global ros_node
    if ros_node is None:
        ros_node = RosServiceNode()
    return ros_node

def spin():
    rclpy.init()  # only once in your process
    ros_node = get_node()
    executor = SingleThreadedExecutor()
    executor.add_node(ros_node)
    executor.spin()
    rclpy.shutdown()

def spin_threaded():
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    return thread
