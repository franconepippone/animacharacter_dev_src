from __future__ import annotations

import rclpy
from rclpy.node import Node
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import GetState, ChangeState

from std_msgs.msg import String
from interfaces.srv import CreateSession
from interfaces.msg import MotionframeArray

from .session_implementations import create_session_manager, ACSessionCreationArguments

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse


SRV_NAME = 'create_session'
CONFIG_TOPIC = 'config_update'
MOTIONFRAME_TOPIC = 'input_motionframes'

HARDWARE_MANAGER_NODE = "/hardware_manager"

class SessManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("session_manager")

        self.get_state_cli = self.create_client(
            GetState,
            f"{HARDWARE_MANAGER_NODE}/get_state"
        )

        self.change_state_cli = self.create_client(
            ChangeState,
            f"{HARDWARE_MANAGER_NODE}/change_state"
        )

        self.get_state_cli.wait_for_service()
        self.change_state_cli.wait_for_service()

        self.srv = self.create_service(
            CreateSession,
            SRV_NAME,
            self.create_session_srv_cb,
        )

        self.motionframe_publisher = self.create_publisher(
            MotionframeArray,
            MOTIONFRAME_TOPIC,
            10,
        )

        self.config_publisher = self.create_publisher(
            String,
            CONFIG_TOPIC,
            10,
        )

        logger_sess_resource = self.get_logger().get_child("resource_manager")
        logger_sess_runner = self.get_logger().get_child("runner")

        # create session manager with custom resource manager and runner objects
        self.session_manager = create_session_manager(
            self.motionframe_publisher,
            self.config_publisher,
            self.validate_session_request_criteria,
            logger_sess_resource,
            logger_sess_runner
        )

        self.get_logger().info("Session manager node initialized.")

    def validate_session_request_criteria(self) -> bool:
        req = ChangeState.Request()
        req.transition.id = Transition.TRANSITION_ACTIVATE

        future = self.change_state_cli.call_async(req)

        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        result = future.result()

        if result is None:
            self.get_logger().error("activate transition failed (no response)")
            return False

        if not result.success:
            self.get_logger().error("activate transition rejected by lifecycle node")
            return False

        self.get_logger().info("hardware_manager activated successfully")
        return True

    # handler for session creation service
    def create_session_srv_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        self.get_logger().info(f"Received session creation request from {request.client_ip}.")

        create_args = ACSessionCreationArguments(
            request.client_ip,
            request.client_udp_port
        )

        result = self.session_manager.new_session(create_args)
        if result.handle is None or not result.success: # on failure to make a new session
            response.success = False
            response.msg = result.error_msg if result.error_msg else "Unknown error"
            self.get_logger().warning(f"Session creation failed: {response.msg}")
            return response

        self.get_logger().info("Session began successfully.")

        context = result.handle.ctx
        response.success = True
        response.tcp_port = context.tcp_port
        response.udp_port = context.stream_port
        response.session_secret = context.session_secret
        return response


def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
