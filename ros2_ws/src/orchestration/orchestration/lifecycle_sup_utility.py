from typing import Optional, TypeVar, Protocol, Callable, cast

import rclpy
from rclpy.task import Future
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.node import Node


def gather_future_results(node: Node, *futures: Future):
    for f in futures:
        rclpy.spin_until_future_complete(node, f)
    
    return tuple([f.result() for f in futures])





ResultT = TypeVar("ResultT", covariant=True)


class TypedFuture(Protocol[ResultT]):
    """A typed view over a ROS Future. Purely static typing."""
    def result(self) -> Optional[ResultT]: ...
    def add_done_callback(self, fn: Callable[[Future], None]) -> None: ...
    def done(self) -> bool: ...


def _make_failed_future() -> TypedFuture[ChangeState.Response]:
    fut = Future()
    response = ChangeState.Response()
    response.success = False
    fut.set_result(response)
    return cast(TypedFuture[ChangeState.Response], fut)


class LifecycleNodeSupervisor:
    """Simple remote API for interacting with a lifecycle-managed node. Ment to
    be instantiated by Supervisory nodes, passing 'self' as first argument."""

    def __init__(self, host_node: Node, target_node_name: str, default_timeout: float = 5.0) -> None:
        self.host_node: Node = host_node
        self.target_node_name: str = target_node_name
        self.timeout = default_timeout

        self._change_state_client = host_node.create_client(
            ChangeState, f"{self.target_node_name}/change_state"
        )
        self._get_state_client = host_node.create_client(
            GetState, f"{self.target_node_name}/get_state"
        )

    def wait_for_services(self, timeout_each: float) -> None:
        """Block until both lifecycle services are available."""
        self._change_state_client.wait_for_service(timeout_sec=timeout_each)
        self._get_state_client.wait_for_service(timeout_sec=timeout_each)

    def is_ready(self) -> bool:
        """Return True when both lifecycle services are ready."""
        return (
            self._change_state_client.service_is_ready()
            and self._get_state_client.service_is_ready()
        )

    def get_state(self) -> Optional[int]:
        """Return the target node's current state id, or None if unavailable."""
        if not self._get_state_client.service_is_ready():
            self.host_node.get_logger().warn(f"get_state service not ready yet for {self.target_node_name}")
            return None

        request = GetState.Request()
        future = self._get_state_client.call_async(request)
        rclpy.spin_until_future_complete(self.host_node, future)

        result = cast(Optional[GetState.Response], future.result())
        if result is None:
            return None

        return result.current_state.id

    def change_state(self, transition_id: int) -> bool:
        """Request a lifecycle transition and return whether it succeeded."""
        if not self._change_state_client.service_is_ready():
            self.host_node.get_logger().warn(f"change_state service not ready yet for {self.target_node_name}")
            return False

        request = ChangeState.Request()
        request.transition.id = transition_id
        future = self._change_state_client.call_async(request)
        rclpy.spin_until_future_complete(self.host_node, future, timeout_sec=self.timeout)

        result = cast(Optional[ChangeState.Response], future.result())
        return bool(result.success) if result is not None else False

    def change_state_async(self, transition_id: int) -> TypedFuture[ChangeState.Response]:
        """Request a lifecycle transition asynchronously and return the ROS future."""

        if not self._change_state_client.service_is_ready():
            self.host_node.get_logger().warn(f"change_state service not ready yet for {self.target_node_name}")
            return _make_failed_future()

        request = ChangeState.Request()
        request.transition.id = transition_id

        # This is already a future-like object compatible with spin_until_future_complete
        future = self._change_state_client.call_async(request)

        return cast(TypedFuture[ChangeState.Response], future)

    def wait_for_future(
        self,
        future: TypedFuture[ResultT],
        timeout_sec: Optional[float] = None,
    ) -> Optional[ResultT]:
        if timeout_sec is None:
            timeout_sec = self.timeout
        rclpy.spin_until_future_complete(
            self.host_node,
            cast(Future, future),
            timeout_sec=timeout_sec,
        )
        return cast(Optional[ResultT], future.result())


    def configure(self) -> bool:
        """Request the CONFIGURE transition."""
        return self.change_state(Transition.TRANSITION_CONFIGURE)

    def activate(self) -> bool:
        """Request the ACTIVATE transition."""
        return self.change_state(Transition.TRANSITION_ACTIVATE)

    def cleanup(self) -> bool:
        """Request the CLEANUP transition."""
        return self.change_state(Transition.TRANSITION_CLEANUP)

    def shutdown(self) -> bool:
        """Request the appropriate SHUTDOWN transition for the current state."""
        state = self.get_state()

        if state is None:
            return False

        if state == State.PRIMARY_STATE_UNCONFIGURED:
            transition = Transition.TRANSITION_UNCONFIGURED_SHUTDOWN
        elif state == State.PRIMARY_STATE_INACTIVE:
            transition = Transition.TRANSITION_INACTIVE_SHUTDOWN
        elif state == State.PRIMARY_STATE_ACTIVE:
            transition = Transition.TRANSITION_ACTIVE_SHUTDOWN
        else:
            self.host_node.get_logger().warn(
                f"Cannot shutdown from lifecycle state {state}"
            )
            return False

        return self.change_state(transition)
    

    # ASYNC API

    def configure_async(self):
        """Request CONFIGURE transition asynchronously."""
        return self.change_state_async(Transition.TRANSITION_CONFIGURE)

    def activate_async(self):
        """Request ACTIVATE transition asynchronously."""
        return self.change_state_async(Transition.TRANSITION_ACTIVATE)

    def cleanup_async(self):
        """Request CLEANUP transition asynchronously."""
        return self.change_state_async(Transition.TRANSITION_CLEANUP)

    def shutdown_async(self):
        """Request SHUTDOWN transition asynchronously."""
        state = self.get_state()

        if state is None:
            return _make_failed_future()

        if state == State.PRIMARY_STATE_UNCONFIGURED:
            transition = Transition.TRANSITION_UNCONFIGURED_SHUTDOWN
        elif state == State.PRIMARY_STATE_INACTIVE:
            transition = Transition.TRANSITION_INACTIVE_SHUTDOWN
        elif state == State.PRIMARY_STATE_ACTIVE:
            transition = Transition.TRANSITION_ACTIVE_SHUTDOWN
        else:
            self.host_node.get_logger().warn(
                f"Cannot shutdown from lifecycle state {state}"
            )
            return _make_failed_future()

        return self.change_state_async(transition)
