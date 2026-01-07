# my_package/node.py
import rclpy
from rclpy.node import Node

import pySerialDevice as dev

class Talker(Node):
    def __init__(self):
        super().__init__('talker')
        self.timer = self.create_timer(1.0, self.tick)
        self.dev = dev.SerialDevice("porcoddio", "COM3", 115200)

    def tick(self):
        self.get_logger().info('Hello from Jazzy')

def main():
    rclpy.init()
    node = Talker()
    rclpy.spin(node)
    rclpy.shutdown()
