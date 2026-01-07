import rclpy

import sys
print(sys.executable)

def main():
    rclpy.init()
    node = rclpy.create_node('my_node')
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()