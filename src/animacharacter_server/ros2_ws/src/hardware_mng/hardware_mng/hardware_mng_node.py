from __future__ import annotations

import json

from diagnostic_updater import Updater
from interfaces.msg import MotionframeArray
from orchestration.heartbeats import HeartbeatGenerator
import rclpy
from rclpy.lifecycle import (
    LifecycleNode,
    State as RosLifecycleState,
    TransitionCallbackReturn,
)
from rclpy.parameter import Parameter
from std_msgs.msg import String
from system_commons import proc_names as process_names

from .controller_manager import ControllerManager


INPUT_TOPIC = 'input_motionframes'
CONFIG_TOPIC = 'config_update'


class HardwareManagerNode(LifecycleNode):
    """
    ROS lifecycle facade around the independently managed hardware plugins.

    ROS lifecycle mapping to controller lifecycle:

    * ``configure`` starts one runner per plugin with an INACTIVE target.
      Startup errors, including unfinalized previous runners, fail the ROS
      transition. If runners start but do not reach INACTIVE before
      ``controller_operation_timeout``, configure warns with their live/target
      states and still succeeds.
    * ``activate`` sets every controller target to ACTIVE. A target-setting
      error fails; otherwise the node becomes active and waits for reconciliation.
      A timeout is a warning, not a failed ROS transition.
    * ``deactivate`` first stops accepting input, then sets INACTIVE targets.
      A target-setting error fails; a reconciliation timeout warns but succeeds.
    * ``cleanup``, ``shutdown``, and ``error`` stop accepting input and set
      FINALIZED targets. A target-setting error fails; otherwise each transition
      waits for finalization and succeeds, warning if it does not reconcile
      before the timeout. Unfinished runners remain tracked for safe teardown.
    """

    def __init__(self) -> None:
        super().__init__('hardware_manager')
        self.declare_parameter(
            'controller_paths', Parameter.Type.STRING_ARRAY
        )
        self.declare_parameter('plugin_dirs', Parameter.Type.STRING_ARRAY)
        self.declare_parameter('strict_mode', False)
        self.declare_parameter('controller_operation_timeout', 10.0)

        controller_paths = list(self.get_parameter('controller_paths').value)
        plugin_dirs = list(self.get_parameter('plugin_dirs').value)
        strict_mode = self.get_parameter('strict_mode').value
        operation_timeout = self.get_parameter(
            'controller_operation_timeout'
        ).value
        if operation_timeout < 0:
            raise ValueError('controller_operation_timeout cannot be negative')

        self.controller_manager = ControllerManager(
            self,
            controller_paths,
            plugin_dirs,
            strict_mode,
            operation_timeout,
        )

        self.updater = Updater(self)
        self.updater.setHardwareID('hardware_manager')
        for controller in self.controller_manager.controllers:
            self.updater.add(
                f'controller-{controller.name}',
                lambda status, ctrl=controller:
                    self.controller_manager.check_controller_status(status, ctrl),
            )
        self.create_timer(1.0, self.updater.update)
        self.hb = HeartbeatGenerator(
            self, 5, 5, process_names.HARDWARE_MANAGER
        )

        self.create_subscription(
            MotionframeArray, INPUT_TOPIC, self.motionframe_callback, 5
        )
        self.create_subscription(
            String, CONFIG_TOPIC, self.update_config_callback, 5
        )
        self.get_logger().info(
            'Loaded '
            f'{len(self.controller_manager.controllers)} hardware controller(s)'
        )

    def update_config_callback(self, message: String) -> None:
        try:
            config = json.loads(message.data)
        except json.JSONDecodeError as error:
            self.get_logger().warning(f'Failed to parse config update: {error}')
            return
        if not isinstance(config, dict):
            self.get_logger().warning('Config update must be a JSON object')
            return
        self.controller_manager.enqueue_config_update(config)

    def motionframe_callback(self, message: MotionframeArray) -> None:
        self.controller_manager.dispatch_motionframes(
            message.ids, message.values
        )

    def on_configure(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug('Configuring hardware controllers')
        if not self.controller_manager.awake():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_activate(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug('Activating hardware controllers')
        if not self.controller_manager.activate():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug('Deactivating hardware controllers')
        if not self.controller_manager.deactivate():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug('Finalizing hardware controllers')
        if not self.controller_manager.shutdown():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug('Shutting down hardware controllers')
        if not self.controller_manager.shutdown():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_error(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().error(
            'Stopping hardware controllers after lifecycle error'
        )
        if not self.controller_manager.handle_error():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def destroy_node(self) -> None:
        if not self.controller_manager.shutdown():
            self.get_logger().error(
                'Some controller threads remain alive during node destruction'
            )
        super().destroy_node()


def main(args: list[str] | None = None) -> None:
    """Initialize ROS and spin the hardware manager lifecycle node."""
    rclpy.init(args=args)
    node: HardwareManagerNode | None = None
    try:
        node = HardwareManagerNode()
        rclpy.spin(node)
    finally:
        try:
            if node is not None:
                node.destroy_node()
        finally:
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == '__main__':
    main()
