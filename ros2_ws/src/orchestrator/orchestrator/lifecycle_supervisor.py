import rclpy
from rclpy.node import Node
from rclpy.duration import Duration

from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition, State


class LifecycleSupervisor(Node):

    def __init__(self, timeout_sec=5.0):
        super().__init__("lifecycle_supervisor")

        self.declare_parameter("target_node", "")
        self.target = self.get_parameter("target_node").value

        if not self.target:
            self.get_logger().fatal("Missing target_node parameter")
            raise SystemExit(1)

        self.timeout = Duration(seconds=timeout_sec)

        self.get_state_cli = self.create_client(
            GetState,
            f"{self.target}/get_state"
        )

        self.change_state_cli = self.create_client(
            ChangeState,
            f"{self.target}/change_state"
        )

        self.timer = self.create_timer(2.0, self.check_state)

        self.get_logger().info(
            f"Supervisor started for {self.target}"
        )

    def check_state(self):
        if not self.get_state_cli.service_is_ready():
            self.get_logger().warn("get_state service not ready yet")
            return

        req = GetState.Request()
        future = self.get_state_cli.call_async(req)
        future.add_done_callback(self.on_state)

    def on_state(self, future):
        result = future.result()

        if result is None:
            self.get_logger().error("failed to get state")
            return

        state = result.current_state

        if state.id >= State.PRIMARY_STATE_INACTIVE:
            return

        self.get_logger().warn(
            f"state {state.label}, configuring..."
        )

        self.try_configure()

    def try_configure(self):
        if not self.change_state_cli.service_is_ready():
            self.get_logger().error("change_state not ready")
            return

        req = ChangeState.Request()
        req.transition.id = Transition.TRANSITION_CONFIGURE

        future = self.change_state_cli.call_async(req)
        future.add_done_callback(self.on_configured)

    def on_configured(self, future):
        result = future.result()

        if result and result.success:
            self.get_logger().info("configured successfully")
        else:
            self.get_logger().fatal("configure failed")
            raise SystemExit(1)


def main():
    rclpy.init()
    node = LifecycleSupervisor(timeout_sec=5.0)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()