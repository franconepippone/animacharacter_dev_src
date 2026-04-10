from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from enum import Enum, auto
from interfaces.msg import MotionframeArray

from .dispatcher import Dispatcher
from .looper import LoopSupervisor, display_status_from_json, LoopDescriptor 
from .abstract_hw_controller import MotionCommand, BaseHardwareController
from .hw_controller_state_reconciler import (
    HWControllerStateReconciler,
    ControllerState
)

# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'

class HardwareManagerNode(LifecycleNode):
    def __init__(self, 
            dispatcher: Dispatcher, 
            looper: LoopSupervisor, 
            loop_controllers_pairs: list[tuple[LoopDescriptor, BaseHardwareController]]
        ):
        super().__init__('hardware_manager')
        self.dispatcher: Dispatcher = dispatcher
        self.looper = looper
        self.loop_controllers_pairs = loop_controllers_pairs # loop and controller are always kept together in a tuple

        # setting up reconciler for background state reconciliation of controller state
        # (if a controller fails to update its state during a lifecycle transistion, this will try to recoincile in the background)
        self.reconciler = HWControllerStateReconciler(
            looper=self.looper,
            logger=self.get_logger()
        )

        for loop, ctrl in loop_controllers_pairs:
            self.reconciler.add_controller(loop, ctrl)

        self.timer = self.create_timer(3, self.reconciler.reconcile, autostart=True)

        #self.create_timer(3, lambda: print(self.reconciler.get_ascii_status()), autostart=True)

        self.sub = self.create_subscription(
            MotionframeArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            5
        )

        self.get_logger().info("Initialized!")

    def motionframe_callback(self, msg: MotionframeArray):
        # create a motion command for each pair, and dispatch them to the queues
        for act_id, val in zip(msg.ids, msg.values):
            #self.get_logger().info(f"{act_id}:{val}")
            self.dispatcher.dispatch(MotionCommand(act_id, val))

    # --- configure ---
    def on_configure(self, state: State):
        self.get_logger().info("on_configure()")
        
        self.reconciler.set_goal_all(
            ControllerState.INITIALIZED
        )
        self.reconciler.reconcile()
        return TransitionCallbackReturn.SUCCESS

    # --- activate ---
    def on_activate(self, state: State):
        self.get_logger().info("on_activate()")

        self.reconciler.set_goal_all(
            ControllerState.RUNNING
        )
        self.reconciler.reconcile()
        return TransitionCallbackReturn.SUCCESS

    # --- deactivate ---
    def on_deactivate(self, state: State):
        self.get_logger().info("on_deactivate()")

        self.reconciler.set_goal_all(
            ControllerState.INITIALIZED
        )
        self.reconciler.reconcile()
        return TransitionCallbackReturn.SUCCESS

    # --- cleanup ---
    def on_cleanup(self, state: State):
        self.get_logger().info("on_cleanup()")
        
        self.reconciler.set_goal_all(
            ControllerState.UNINITIALIZED
        )
        self.reconciler.reconcile()
        return TransitionCallbackReturn.SUCCESS

    # --- shutdown ---
    def on_shutdown(self, state: State):
        self.get_logger().info("on_shutdown()")
        self.reconciler.set_goal_all(
            ControllerState.UNINITIALIZED
        )
        self.reconciler.reconcile()
        self.reconciler.reconcile()
        return TransitionCallbackReturn.SUCCESS

    # --- error ---
    def on_error(self, state: State):
        self.get_logger().info("on_error()")
        return TransitionCallbackReturn.SUCCESS




