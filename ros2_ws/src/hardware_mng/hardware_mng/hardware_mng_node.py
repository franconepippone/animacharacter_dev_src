import rclpy
from rclpy.node import Node
from std_msgs.msg import ByteMultiArray  # example

from .dispatcher import Dispatcher


INPUT_TOPIC = 'input_motionframes'

class HardwareManagerNode(Node):
    def __init__(self, dispatcher: Dispatcher):
        super().__init__('hardware_manager')
        self.dispatcher = dispatcher

        self.sub = self.create_subscription(
            ByteMultiArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            10
        )

    def motionframe_callback(self, msg: ByteMultiArray):
        # TODO parse the data into motion commands tuples, and we create a motionframe
        motionframe = []

        self.dispatcher.dispatch_multiple(motionframe)

