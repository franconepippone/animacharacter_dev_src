from typing import Optional, TypeVar, Protocol, Callable, cast
import time

import rclpy
from rclpy.task import Future
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup


ResultT = TypeVar("ResultT")


def _make_failed_response() -> ChangeState.Response:
    response = ChangeState.Response()
    response.success = False
    return response

def _make_failed_future() -> Future[ChangeState.Response]:
    fut: Future[ChangeState.Response] = Future()
    fut.set_result(_make_failed_response())
    return fut


class LifecycleNodeSupervisor:
    """Simple remote API for interacting with a lifecycle-managed node. Ment to
    be instantiated by Supervisory nodes, passing 'self' as first argument."""

    def __init__(self, host_node: Node, target_node_name: str) -> None:
        self.host_node: Node = host_node
        self.target_node_name: str = target_node_name
        self.logger = host_node.get_logger().get_child(f'lfcyclesup__{target_node_name[1:]}')

        group = ReentrantCallbackGroup()
        self._change_state_client = host_node.create_client(
            ChangeState, f"{self.target_node_name}/change_state",
            callback_group=group
        )
        self._get_state_client = host_node.create_client(
            GetState, f"{self.target_node_name}/get_state",
            callback_group=group
        )

    def wait_readyness(self, timeout_each: float) -> None:
        """Block until both lifecycle services are available."""
        self._change_state_client.wait_for_service(timeout_sec=timeout_each)
        self._get_state_client.wait_for_service(timeout_sec=timeout_each)

    def is_ready(self) -> bool:
        """Return True when both lifecycle services are ready."""
        return (
            self._change_state_client.service_is_ready()
            and self._get_state_client.service_is_ready()
        )

    async def get_state(self) -> Optional[int]:
        """Return the target node's current state id, or None if unavailable."""

        if not self._get_state_client.service_is_ready():
            self.logger.warn(f"get_state service not ready yet for {self.target_node_name}")
            return None

        request = GetState.Request()
        resp = cast(
            GetState.Response,
            await self._get_state_client.call_async(request)
        ) 

        return resp.current_state.id

    async def change_state(self, transition_id: int) -> ChangeState.Response:
        """Request a lifecycle transition asynchronously and return the ROS future."""

        if not self._change_state_client.service_is_ready():
            self.logger.warn(f"change_state service not ready yet for {self.target_node_name}")
            return _make_failed_response()

        request = ChangeState.Request()
        request.transition.id = transition_id

        resp = cast(
            ChangeState.Response,
            await self._change_state_client.call_async(request)
        ) 

        return resp

    async def configure(self):
        """Request the CONFIGURE transition."""
        resp = await self.change_state(Transition.TRANSITION_CONFIGURE)
        return bool(resp.success)

    async def activate(self):
        """Request the ACTIVATE transition."""
        resp = await self.change_state(Transition.TRANSITION_ACTIVATE)
        return bool(resp.success)
    
    async def cleanup(self):
        """Request the CLEANUP transition."""
        resp = await self.change_state(Transition.TRANSITION_CLEANUP)
        return bool(resp.success)
    
    async def shutdown(self):
        """Request the appropriate SHUTDOWN transition for the current state."""
        state = await self.get_state()

        if state is None:
            return False

        if state == State.PRIMARY_STATE_UNCONFIGURED:
            transition = Transition.TRANSITION_UNCONFIGURED_SHUTDOWN
        elif state == State.PRIMARY_STATE_INACTIVE:
            transition = Transition.TRANSITION_INACTIVE_SHUTDOWN
        elif state == State.PRIMARY_STATE_ACTIVE:
            transition = Transition.TRANSITION_ACTIVE_SHUTDOWN
        else:
            self.logger.warning(
                f"Cannot shutdown from lifecycle state {state}"
            )
            return False
        
        resp = await self.change_state(transition)
        return bool(resp.success)