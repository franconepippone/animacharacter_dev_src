import json
import os
import psutil

from rclpy.lifecycle import LifecycleNode
from rclpy.lifecycle import State
from rclpy.lifecycle import TransitionCallbackReturn
from std_msgs.msg import ByteMultiArray, String
from std_srvs.srv import Trigger, Trigger_Request, Trigger_Response

from interfaces.msg import MotionframeArray

from .dispatcher import BatchDispatcher
from .looper import ThreadedLooper, display_status_from_json

# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'

class HardwareManagerNode(LifecycleNode):
    def __init__(self, batch_dispatcher: BatchDispatcher, looper: ThreadedLooper):
        super().__init__('hardware_manager')
        self.batch_dispatcher = batch_dispatcher
        self.looper = looper

        self.srv = self.create_service(
            Trigger,
            '/get_status',
            self.get_status_callback
        )

        self.sub = self.create_subscription(
            MotionframeArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            10
        )
        self.get_logger().info("Initialized!")

    def get_status_callback(self, request: Trigger_Request, response: Trigger_Response):
        """
        Utility service to be called from CLI to get a json representation of the status
        of the hardware manager
        """
        # construct the json dict
        status = {
            'pid' : os.getpid(),
            'looper' : self.looper.status_as_json()
        }
        
        try:
            json_str = json.dumps(status)
        except Exception as e:
            response.message = str(e)
            response.success = False
            return response
    
        response.success = True
        response.message = json_str
        return response

    def motionframe_callback(self, msg: MotionframeArray):
        # TODO parse the data into motion commands tuples, and we create a motionframe

        # array of tuples (actutator id: int, actuator target value: float)
        motionframes = [(act_id, val) for act_id, val in zip(msg.ids, msg.values)]
        
        self.batch_dispatcher.dispatch(motionframes)

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
