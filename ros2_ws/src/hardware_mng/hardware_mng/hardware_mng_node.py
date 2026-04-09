from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from interfaces.msg import MotionframeArray

from .dispatcher import BatchDispatcher, Dispatcher
from .looper import LoopSupervisor, display_status_from_json
from .abstract_hw_controller import MotionCommand


# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'

class HardwareManagerNode(LifecycleNode):
    def __init__(self, batch_dispatcher: BatchDispatcher, looper: LoopSupervisor):
        super().__init__('hardware_manager')
        self.batch_dispatcher = batch_dispatcher
        self.dispatcher: Dispatcher = Dispatcher()
        self.looper = looper

        self.sub = self.create_subscription(
            MotionframeArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            10
        )
        self.get_logger().info("Initialized!")

    def motionframe_callback(self, msg: MotionframeArray):
        # create a motion command for each pair, and dispatch them to the queues        
        for act_id, val in zip(msg.ids, msg.values):
            self.dispatcher.dispatch(MotionCommand(act_id, val))

    # --- configure ---
    def on_configure(self, state: State):
        self.get_logger().info("on_configure()")
        
        # start looper threads in a ready state
        self.looper.start_all(paused=True)
        ok = self.looper.all_running()
        print(display_status_from_json(self.looper.status_as_json()))



        return TransitionCallbackReturn.SUCCESS if ok else TransitionCallbackReturn.FAILURE

    # --- activate ---
    def on_activate(self, state: State):
        self.get_logger().info("on_activate()")
        self.looper.unpause_all()
        print(display_status_from_json(self.looper.status_as_json()))
        return TransitionCallbackReturn.SUCCESS

    # --- deactivate ---
    def on_deactivate(self, state: State):
        self.get_logger().info("on_deactivate()")
        self.looper.pause_all()
        print(display_status_from_json(self.looper.status_as_json()))
        return TransitionCallbackReturn.SUCCESS

    # --- cleanup ---
    def on_cleanup(self, state: State):
        self.get_logger().info("on_cleanup()")
        self.looper.stop_all()
        ok = self.looper.all_stopped()
        print(display_status_from_json(self.looper.status_as_json()))
        return TransitionCallbackReturn.SUCCESS if ok else TransitionCallbackReturn.FAILURE

    # --- shutdown ---
    def on_shutdown(self, state: State):
        self.get_logger().info("on_shutdown()")
        self.looper.stop_all()
        print(display_status_from_json(self.looper.status_as_json()))
        return TransitionCallbackReturn.SUCCESS

    # --- error ---
    def on_error(self, state: State):
        self.get_logger().info("on_error()")
        return TransitionCallbackReturn.SUCCESS
