import rclpy
from rclpy.node import Node
from interfaces.msg import MotionframeArray
from std_msgs.msg import String
import random

import json

# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'
CONFIG_TOPIC = 'config_update'

class MinimalPublisher(Node):
    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher = self.create_publisher(MotionframeArray, INPUT_TOPIC, 10)
        self.cfg_publisher = self.create_publisher(String, CONFIG_TOPIC, 10)
        self.timer = self.create_timer(1.0 / 1, self.timer_callback)
        self.count = 0

    def timer_callback(self):

        msg = MotionframeArray()
        msg.ids = (1,2,3,4,5,6,7)
        msg.values = [round(random.random(), 2) for _ in range(len(msg.ids))]
        self.publisher.publish(msg)
        self.get_logger().info(f"Publishing: message {self.count} {msg.ids} {msg.values}")
        self.count += 1

        



def main():
    rclpy.init()
    node = MinimalPublisher()
    rclpy.spin(node)
    rclpy.shutdown()