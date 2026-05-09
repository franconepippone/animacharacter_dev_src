from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from interfaces.srv import CreateSession
from interfaces.msg import MotionframeArray

from .session_implementations import ACSessionContext, ACSessionRunner, ACSessResourceMng
from .session import SessionManager

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse


SRV_NAME = 'create_session'
CONFIG_TOPIC = 'config_update'

class SessManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("sess_manager_node")

        self.srv = self.create_service(
            CreateSession,
            SRV_NAME,
            self.create_session_srv_cb,
        )

        self.motionframe_publisher = self.create_publisher(
            MotionframeArray,
            'input_motionframes',
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
        self.session_manager = SessionManager(
            sess_resource_manager=ACSessResourceMng(logger=logger_sess_resource),
            sess_runner=ACSessionRunner(
                self.motionframe_publisher, 
                self.config_publisher,
                logger=logger_sess_runner
            ),
            session_creation_criteria=self.validate_session_request_criteria
        )

        self.get_logger().info("Session manager node initialized.")

    def validate_session_request_criteria(self) -> bool:
        # XXX TODO check for hardware avaliablility
        return True

    # handler for session creation service
    def create_session_srv_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        self.get_logger().info(f"Received session creation request from {request.client_info}.")

        result = self.session_manager.new_session()
        if result.handle is None or not result.success: # on failure to make a new session
            response.success = False
            response.msg = result.error_msg if result.error_msg else "Unknown error"
            self.get_logger().warning(f"Session creation failed: {response.msg}")
            return response

        self.get_logger().info("Session began successfully.")

        context: ACSessionContext = result.handle.ctx
        response.success = True
        response.nng_port = context.tcp_port
        response.sudp_port = context.stream_port
        response.sudp_secret_key = context.session_secret
        response.token = context.session_secret #TODO XXX REMOVE
        return response


def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
