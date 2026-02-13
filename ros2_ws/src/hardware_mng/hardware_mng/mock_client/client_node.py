import rclpy
from rclpy.node import Node
from interfaces.msg import MotionframeArray
import random

# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'

class MinimalPublisher(Node):
    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher = self.create_publisher(MotionframeArray, INPUT_TOPIC, 10)
        self.timer = self.create_timer(1.0 / 50, self.timer_callback)
        self.count = 0

    def timer_callback(self):

        msg = MotionframeArray()
        msg.ids = (50,51,52,53, 100, 101, 105)
        msg.values = [round(random.random(), 2) for _ in range(len(msg.ids))]
        self.publisher.publish(msg)
        self.get_logger().info(f"Publishing: message {self.count}")
        self.count += 1

def main():
    rclpy.init()
    node = MinimalPublisher()
    rclpy.spin(node)
    rclpy.shutdown()