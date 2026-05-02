from __future__ import annotations
from dataclasses import dataclass
import rclpy
from rclpy.node import Node
import threading
from typing import TYPE_CHECKING

from .session_manager import SessionContext, SessionManager

from interfaces.srv import CreateSession
from interfaces.msg import MotionframeArray

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
        self.session_manager = SessionManager()
        self.get_logger().debug("Session manager instantiated.")
        # publisher to pass to the session runner ---------> self.create_publisher()

        self.srv = self.create_service(
            CreateSession,
            SRV_NAME,
            self.create_session_srv_cb
        )

        self.motionframe_publisher = self.create_publisher(
            MotionframeArray,
            'input_motionframes',
            10
        )

        self.get_logger().info(F"Session manager node initialized.")
    
    def _motionframe_forwarder(self, ctx: SessionContext, stop_event: threading.Event):
        """
        This method runs threaded inside _run_session. It's responsible for receiving motionframes
        from the dedicated socket and republishing them to the ros2 topic"""

        while not stop_event.is_set():
            try:
                # this should have a regular timeout interval
                motionframes_raw = ctx.stream_sock.recv()
            except Exception as e:
                self.get_logger().error(f"Error receiving motionframes: {e}")
                continue
            # we can catch not fatal exception and keep the loop running
            
            # do magic to convert
            MotionframeArray_msg = MotionframeArray()
            self.motionframe_publisher.publish(MotionframeArray_msg)
        
        stop_event.set() # if we crash, make sure everything stops

    def _run_session(self, ctx: SessionContext, stop_event: threading.Event):

        # start motionframe forwarder
        t_stream = threading.Thread(target=self._motionframe_forwarder, args=(ctx, stop_event), daemon=True)
        t_stream.start()

        # do more, potentially more threads

        t_stream.join()


    def validate_session_request_criteria(self, request: CreateSessionRequest) -> ValidationOutcome:
        """
        Validates if the current system state allows for a new session to be created.
        
        This method checks various criteria such as:
        - No ongoing session is active
        - Hardware resources are available and ready

        Returns True if all criteria are met, False otherwise.
        """
        if self.session_manager.is_session_active():
            reason = "An active session is already ongoing."
            return ValidationOutcome(valid=False, reason=reason)
        
        # Additional hardware/resource checks can be added here

        return ValidationOutcome(valid=True)

    def create_session_srv_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        """
        Callback for the session creation request ROS2 service.

        This method validates the request and delegates session lifecycle
        management to the internal SessionManager.

        If a session can be created, the manager allocates resources, starts the
        runner, and the response is populated with the session coordinates.
        Otherwise the response contains a failure reason.
        """
        
        self.get_logger().info(f"Received session creation request from {request.client_info}.")

        # ASSERTS if state is valid (no ongoing session, hardware ready, etc...)
        validation_result = self.validate_session_request_criteria(request)
        if not validation_result.valid:
            response.success = False
            response.msg = f"Session creation request denied due to: {validation_result.reason}"
            self.get_logger().warning(response.msg)
            return response

        # if all criteria are met, build and start a new session
        result = self.session_manager.new_session()
        if not result.success or result.context is None:
            response.success = False
            response.msg = result.error_msg if result.error_msg else "Unknown error"
            self.get_logger().warning(f"Session creation failed: {response.msg}")
            return response

        self.get_logger().info("Session began successfully.")
        
        # construct response with session data
        response.success = True
        response.nng_port = result.context.nng_port
        response.sudp_port = result.context.stream_port
        response.sudp_secret_key = result.context.stream_secret_key
        response.token = result.context.secret_token

        return response

    def destroy_session(self, context: SessionContext) -> bool:
        """
        Callback provided to the session runner to be invoked when session termination is required.
        This method delegates cleanup to the session manager and ensures the active
        session is released.
        """
        self.get_logger().info(f"Destroying session {context}")
        success = self.session_manager.terminate_session()
        if success:
            self.get_logger().info("Session successfully destroyed.")
        return success



def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()