# my_package/node.py
import rclpy
from rclpy.node import Node

class Talker(Node):
    def __init__(self):
        super().__init__('talker')
        self.timer = self.create_timer(1.0, self.tick)

    def tick(self):
        self.get_logger().info('Hello from Jazzy')

def main():
    rclpy.init()
    node = Talker()
    rclpy.spin(node)
    rclpy.shutdown()
