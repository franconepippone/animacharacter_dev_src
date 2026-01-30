from __future__ import annotations

import rclpy
from rclpy.node import Node

from typing import TYPE_CHECKING

from session_mng.sess_creator import SessionCreator
from session_mng.sess_runner import SessionRunner

from interfaces.srv import CreateSession # Replace with actual service type

if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse

class SessManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("sess_manager_node")
        self.sess_creator = SessionCreator(self.get_logger())
        self.get_logger().info("Session Manager Node instantiated.")
        self.sess_runner = SessionRunner(self.get_logger())
        self.get_logger().info("Session Runner Node instantiated.")

        self.srv = self.create_service(
            CreateSession,
            'create_session',
            self.create_session_cb
        )

    def create_session_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        """
        Callback for the session creation request ros2 service.   
        
        This gets called from the http authenticator server node when a request to create a new
        session is received from a remote client, and the apikey is valid. 
        
        This method uses the SessionCreator object to attempt to create a new session:
        - if successfull, it reponds to the srv client with a success states, providing valid session coordinates (secret token, tcp and udp ports);
        - if unsuccessfull, it responds with a failure state and info.
         
        In the case of a succesfull session creation, before responding to the srv client, this method also 
        invokes the SessionRunner.start method with the current session context (open sockets and tokens),
        that begins the core session logic processing loop in a separate thread (this is what actually runs the session)
        
        After returning, it's now the job of the srv client (the http authenticator server node) to forward success/error info to the remote client.
        """
        self.get_logger().info(f"Received session creation request from {request.client_info}.")
        result = self.sess_creator.create_session()

        if not result.success or result.context is None:
            response.success = False
            response.msg = result.error_msg if result.error_msg else "Unknown error"
            self.get_logger().error(f"Session creation failed: {response.msg}")
            return response
            
        # type hints now provided via TYPE_CHECKING imports
        response.success = True
        response.nng_port = result.context.nng_port
        response.sudp_port = result.context.stream_port
        response.sudp_secret_key = result.context.stream_secret_key
        response.token = result.context.secret_token
        self.get_logger().info("Session created successfully.")

        # OPT.A in here we should start the session runner with the context (in a separate thread)
        #  
        # OPT.B session runner is already listening for session, directly from the sess creator object (awaiting a future?)

        # OPT. A (this does not block, just spawns a new thread)
        self.sess_runner.run(result.context)

        return response




def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()