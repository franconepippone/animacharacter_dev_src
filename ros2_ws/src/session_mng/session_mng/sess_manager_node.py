from __future__ import annotations
from dataclasses import dataclass
import rclpy
from rclpy.node import Node

from typing import TYPE_CHECKING

from session_mng.sess_creator import SessionCreationResult, SessionCreator, SessionContext
from session_mng.sess_runner import SessionRunner

from interfaces.srv import CreateSession # Replace with actual service type

if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse


SRV_NAME = 'create_session'

@dataclass
class ValidationOutcome:
    valid: bool
    reason: str | None = None

class SessManagerNode(Node):
    def __init__(self) -> None:
        super().__init__("sess_manager_node")
        self.active_session: SessionContext | None = None
        self.sess_creator = SessionCreator()
        self.get_logger().debug("Session Creator object instantiated.")
        # publisher to pass to the session runner ---------> self.create_publisher()
        self.sess_runner = SessionRunner()
        self.get_logger().debug("Session Runner object instantiated.")


        self.srv = self.create_service(
            CreateSession,
            SRV_NAME,
            self.create_session_cb
        )
        self.get_logger().info(F"Session manager node initialized.")
    
    def validate_session_request_criteria(self, request: CreateSessionRequest) -> ValidationOutcome:
        """
        Validates if the current system state allows for a new session to be created.
        
        This method checks various criteria such as:
        - No ongoing session is active
        - Hardware resources are available and ready

        Returns True if all criteria are met, False otherwise.
        """
        if self.active_session is not None:
            reason = "An active session is already ongoing."
            return ValidationOutcome(valid=False, reason=reason)
        
        # Additional hardware/resource checks can be added here

        return ValidationOutcome(valid=True)

    def set_active_session(self, context: SessionContext) -> None:
        """
        Sets the current active session context.  
        If a session is already active, logs a warning and does not overwrite it (this should never happen).
        """
        if self.active_session is not None:
            self.get_logger().warning("Attempted to set a new active session while another is ongoing; destroy the current one first.")
            return
        self.active_session = context
        self.get_logger().debug("Set new active session context.")

    def create_session_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        """
        Callback for the session creation request ros2 service.   
        
        This gets called from the http authenticator server node when a request to create a new
        session is received and accepted (valid key) from a remote client.
        
        This method first validates if the current system state allows for a new session to be created;
        then it uses the SessionCreator object to to create a new session:
        - if successfull, it reponds to the srv client with a success states, providing valid session coordinates (secret token, tcp and udp ports);
        - if unsuccessfull, it responds with a failure state and info.
         
        In the case of a succesfull session creation, before responding to the srv client, this method also 
        instantiates and invokes the SessionRunner.run method with the current session context (open sockets and tokens),
        that begins the core session logic processing loop in a separate thread (this is what actually runs the session)
        
        After returning, it's now the job of the srv client (the http authenticator server node) to forward success/error info to the remote client.
        """
        
        self.get_logger().info(f"Received session creation request from {request.client_info}.")

        # ASSERTS if state is valid (no ongoing session, hardware ready, etc...)
        validation_result = self.validate_session_request_criteria(request)
        if not validation_result.valid:
            response.success = False
            response.msg = f"Session creation request denied due to: {validation_result.reason}"
            self.get_logger().warning(response.msg)
            return response

        # if all criteria are met, build a new session
        result = self.sess_creator.create_session()
        if not result.success or result.context is None:
            response.success = False
            response.msg = result.error_msg if result.error_msg else "Unknown error"
            self.get_logger().warning(f"Session creation failed: {response.msg}")
            return response
        
        self.set_active_session(result.context)
        self.get_logger().info("Session context created successfully.")
            
        # OPT.A in here we should start the session runner with the context (in a separate thread)
        #  
        # OPT.B session runner is already listening for session, directly from the sess creator object (awaiting a future?)

        # OPT. A (this does not block, just spawns a new thread)
        self.sess_runner = SessionRunner() # new instance to avoid state issues
        self.sess_runner.on_session_termination(self.destroy_session)
        self.sess_runner.run(result.context)
        self.get_logger().info("Session runner started with the new session context.")
        
        # costruct response with session data
        response.success = True
        response.nng_port = result.context.nng_port
        response.sudp_port = result.context.stream_port
        response.sudp_secret_key = result.context.stream_secret_key
        response.token = result.context.secret_token

        return response

    def destroy_session(self, context: SessionContext) -> bool:
        """
        Callback provided to the session runner to be invoked when a session termination is required.
        This method uses the SessionCreator object to destroy the provided session context, freeing sockets and other resources.
        """
        self.get_logger().info(f"Destroying session {context}")
        success = self.sess_creator.destroy_session(context)
        if success:    
            self.active_session = None
        return success



def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()