from __future__ import annotations

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn

from std_msgs.msg import String
from interfaces.srv import CreateSession
from interfaces.msg import MotionframeArray
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from orchestration.lifecycle_sup_utility import LifecycleNodeSupervisor, State, Transition
from orchestration.heartbeats import HeartbeatGenerator
from system_alerts import SysAlertsClient, Level

from system_commons import alert_codes as ac
from system_commons import proc_names as pn

from .session_implementations import create_session_manager, ACSessionCreationArguments, SessionHandle, ACSessionContext



from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from interfaces.srv._create_session import CreateSession_Request as CreateSessionRequest
    from interfaces.srv._create_session import CreateSession_Response as CreateSessionResponse


SRV_NAME = 'create_session'
CONFIG_TOPIC = 'config_update'
MOTIONFRAME_TOPIC = 'input_motionframes'

HARDWARE_MANAGER_NODE = "/hardware_manager"

class SessManagerNode(LifecycleNode):
    def __init__(self) -> None:
        super().__init__("session_manager")
        self._is_active: bool = False

        # TODO eventually move this to configure. Make use of create_lifecycle_publisher for automatic gating when activated
        self.hwmng_sup = LifecycleNodeSupervisor(self, HARDWARE_MANAGER_NODE)

        cbg = MutuallyExclusiveCallbackGroup()

        # hook service for connection listener session creation request
        self.srv = self.create_service(
            CreateSession,
            SRV_NAME,
            self.create_session_srv_cb, # type: ignore
            callback_group=cbg
        )

        # hb automatic generator
        self.hb = HeartbeatGenerator(self, period=5, tolerance=5, name=pn.SESSION_MANAGER)

        # Alert client for raising alerts
        self.alert_cli = SysAlertsClient(self)

        ### =========================
        ### PUBS FOR MOTION DATA AND CONFIGS
        ### =========================

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

        ### ==============================
        ### SESSION MANAGEMENT OBJECTS
        ### ==============================

        logger_sess_resource = self.get_logger().get_child("resource_manager")
        logger_sess_runner = self.get_logger().get_child("runner")

        # create session manager with custom resource manager and runner objects
        self.session_manager = create_session_manager(
            self.motionframe_publisher,
            self.config_publisher,
            self.validate_session_request_criteria,
            self.cleanup_session,
            lambda: self.executor,
            logger_sess_resource,
            logger_sess_runner
        )

        self.get_logger().info("Session manager node initialized.")

    async def cleanup_session(self, handle: SessionHandle[ACSessionContext]):
        """Method scheduled to run after a session ends, either intentionally or abruptly."""

        state_resp = await self.hwmng_sup.change_state_async(Transition.TRANSITION_DEACTIVATE, timeout=5.0)
        if not state_resp.success:
            self.get_logger().error("Hardware manager was unable to be deactivated during cleanup")

        if handle.crash_exception is not None:
            pass

        self.alert_cli.raise_alert(Level.INFO, self.get_name(), ac.INF_SESSION_CLOSURE_OK, 1.0,
            brief="session terminated")
        self.get_logger().info("Session cleaned up.")

    async def validate_session_request_criteria(self) -> bool:
        if not self.hwmng_sup.is_ready():
            self.get_logger().error("Hardware manager is not ready (lifecycle services unavailable)")
            return False

        state_resp = await self.hwmng_sup.change_state_async(Transition.TRANSITION_ACTIVATE, timeout=5.0)
        if not state_resp.success:
            self.get_logger().error("Hardware manager was unable to be activated")
            return False

        self.get_logger().info("hardware_manager activated successfully")
        return True

    # handler for session creation service
    async def create_session_srv_cb(self, request: CreateSessionRequest, response: CreateSessionResponse) -> CreateSessionResponse:
        self.get_logger().info(f"Received session creation request from {request.client_ip}.")
        self.alert_cli.raise_alert(
            Level.INFO, 
            self.get_name(),
            ac.INF_SESSION_CREATION_REQUEST, 
            brief="New session creation was requested",
            description=f"A session request from ip {request.client_ip} was made."
        )

        if not self._is_active:
            response.success = False
            response.msg = "Session manager is not active"
            self.get_logger().warning("Create session rejected because the session manager node is not active.")
            self._raise_session_fail_alert("Create session rejected because the session manager node is not active.") # alert
            return response

        create_args = ACSessionCreationArguments(
            request.client_ip,
            request.client_udp_port
        )

        result = await self.session_manager.new_session(create_args)

        if result is None or result.success is False or result.handle is None: # on failure to make a new session
            response.success = False
            response.msg = result.error_msg if (result is not None and result.error_msg is not None) else "Unknown error"
            self.get_logger().warning(f"Session creation failed: {response.msg}")
            self._raise_session_fail_alert(f"Session creation failed: {response.msg}")
            return response

        self.get_logger().info("Session began successfully.")
        self.alert_cli.raise_alert(
            Level.INFO, 
            self.get_name(),
            ac.INF_SESSION_CREATION_OK, 
            brief='session began'
        )

        context = result.handle.ctx
        response.success = True
        response.tcp_port = context.tcp_port
        response.udp_port = context.stream_port
        response.session_secret = context.session_secret
        return response

    ### LIFECYCLE HOOKS

    def on_activate(self, state):
        self._is_active = True
        self.get_logger().info("Node is now ACTIVE")
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state):
        self._is_active = False
        self.get_logger().info("Node is now INACTIVE")
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state):
        self._is_active = False
        return TransitionCallbackReturn.SUCCESS

    def on_error(self, state):
        self._is_active = False
        return TransitionCallbackReturn.ERROR

    ### UTILITY

    def _raise_session_fail_alert(self, reason: str = ''):
        self.alert_cli.raise_alert(
            level=Level.ERR,
            src=self.get_name(),
            code=ac.ERR_SESSION_CREATION_FAILED,
            ttl=1.0,
            brief=reason
        )


def main(args=None):
    rclpy.init(args=args)
    node = SessManagerNode()
    rclpy.spin(node)
    node.destroy_node()

    rclpy.shutdown()
