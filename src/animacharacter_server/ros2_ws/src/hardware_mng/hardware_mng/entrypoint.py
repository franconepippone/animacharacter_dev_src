import rclpy

from .hardware_mng_node import HardwareManagerNode


def main(args: list[str] | None = None) -> None:
    """Initialize ROS and spin the hardware manager lifecycle node."""
    rclpy.init(args=args)
    node: HardwareManagerNode | None = None
    try:
        node = HardwareManagerNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
