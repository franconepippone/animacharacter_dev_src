import rclpy
from rclpy.lifecycle import LifecycleNode
from rclpy.lifecycle import State
from rclpy.lifecycle import TransitionCallbackReturn
from std_msgs.msg import ByteMultiArray  # example

from .dispatcher import Dispatcher
from .looper_util import ThreadedLooper

INPUT_TOPIC = 'input_motionframes'

class HardwareManagerNode(LifecycleNode):
    def __init__(self, dispatcher: Dispatcher, looper: ThreadedLooper):
        super().__init__('hardware_manager')
        self.dispatcher = dispatcher
        self.looper = looper

        self.sub = self.create_subscription(
            ByteMultiArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            10
        )
        self.get_logger().info("Spinning!")

    def motionframe_callback(self, msg: ByteMultiArray):
        # TODO parse the data into motion commands tuples, and we create a motionframe
        motionframe = []

        self.dispatcher.dispatch_multiple(motionframe)

    # --- configure ---
    def on_configure(self, state: State):
        self.get_logger().info("on_configure()")
        self.looper.start_all(paused=True)
        ok = self.looper.all_running()
        print(self.looper.display_status())
        return TransitionCallbackReturn.SUCCESS if ok else TransitionCallbackReturn.FAILURE

    # --- activate ---
    def on_activate(self, state: State):
        self.get_logger().info("on_activate()")
        self.looper.unpause_all()
        print(self.looper.display_status())
        return TransitionCallbackReturn.SUCCESS

    # --- deactivate ---
    def on_deactivate(self, state: State):
        self.get_logger().info("on_deactivate()")
        self.looper.pause_all()
        print(self.looper.display_status())
        return TransitionCallbackReturn.SUCCESS

    # --- cleanup ---
    def on_cleanup(self, state: State):
        self.get_logger().info("on_cleanup()")
        self.looper.stop_all()
        ok = self.looper.all_stopped()
        print(self.looper.display_status())
        return TransitionCallbackReturn.SUCCESS if ok else TransitionCallbackReturn.FAILURE

    # --- shutdown ---
    def on_shutdown(self, state: State):
        self.get_logger().info("on_shutdown()")
        self.looper.stop_all()
        print(self.looper.display_status())
        return TransitionCallbackReturn.SUCCESS

    # --- error ---
    def on_error(self, state: State):
        self.get_logger().info("on_error()")
        return TransitionCallbackReturn.SUCCESS
