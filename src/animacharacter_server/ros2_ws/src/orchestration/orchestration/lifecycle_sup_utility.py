from typing import Optional, TypeVar, Protocol, Callable, cast
import time

import rclpy
from rclpy.task import Future
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from orchestration.ros_async_utils import wait_future

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

    async def get_state(self, timeout: float = 1000) -> Optional[int]:
        """Return the target node's current state id, or None if unavailable."""

        if not self._get_state_client.service_is_ready():
            self.logger.warning(f"get_state service not ready yet for {self.target_node_name}")
            return None

        request = GetState.Request()
        resp = cast(
            GetState.Response | None,
            await wait_future(self.host_node, self._get_state_client.call_async(request), timeout)
        ) 

        if resp is None:
            # timed out or service failed to respond
            self.logger.debug(f"get_state call returned no response for {self.target_node_name}")
            return None

        return resp.current_state.id

    async def change_state(self, transition_id: int, timeout: float = 1000) -> ChangeState.Response:
        """Request a lifecycle transition asynchronously and return the ROS future."""

        if not self._change_state_client.service_is_ready():
            self.logger.warning(f"change_state service not ready yet for {self.target_node_name}")
            return _make_failed_response()

        request = ChangeState.Request()
        request.transition.id = transition_id

        resp = cast(
            ChangeState.Response | None,
            await wait_future(self.host_node, self._change_state_client.call_async(request), timeout)
        ) 

        if resp is None:
            # timed out or service failed to respond
            self.logger.debug(f"change_state call returned no response for {self.target_node_name}")
            return _make_failed_response()

        return resp

    async def configure(self, timeout: float = 1000):
        """Request the CONFIGURE transition."""
        resp = await self.change_state(Transition.TRANSITION_CONFIGURE, timeout)
        return bool(resp.success)

    async def activate(self, timeout: float = 1000):
        """Request the ACTIVATE transition."""
        resp = await self.change_state(Transition.TRANSITION_ACTIVATE, timeout)
        return bool(resp.success)
    
    async def cleanup(self, timeout: float = 1000):
        """Request the CLEANUP transition."""
        resp = await self.change_state(Transition.TRANSITION_CLEANUP, timeout)
        return bool(resp.success)
    
    async def shutdown(self, timeout_each: float = 1000):
        """Request the appropriate SHUTDOWN transition for the current state.  
        timeout_each is used both for get_state and change_state, meaning worst-case await time is double that.
        """
        state = await self.get_state(timeout_each)

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
        
        resp = await self.change_state(transition, timeout_each)
        return bool(resp.success)