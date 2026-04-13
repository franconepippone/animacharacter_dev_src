from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from enum import Enum, auto
from interfaces.msg import MotionframeArray

from diagnostic_updater import Updater
from diagnostic_updater import DiagnosticStatusWrapper, DiagnosticStatus

from .dispatcher import Dispatcher
from .looper import LoopSupervisor, display_status_from_json, LoopDescriptor 
from .abstract_hw_controller import MotionCommand, BaseHardwareController
from .hw_controller_state_reconciler import (
    HWControllerStateReconciler,
    ControllerState,
    ManagedController
)
from .utils import flatten_for_diagnostics

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
        self._is_active = False

        # ------------------------
        # Controller state automatic reconciliation
        # -----------------------

        # setting up reconciler for background state reconciliation of controller state
        # (if a controller fails to update its state during a lifecycle transistion, this will try to recoincile in the background)
        self.reconciler = HWControllerStateReconciler(
            looper=self.looper,
            logger=self.get_logger()
        )

        for loop, ctrl in loop_controllers_pairs:
            self.reconciler.add_controller(loop, ctrl)

        self.reconcile_timer = self.create_timer(3, self.reconciler.reconcile, autostart=True)
        
        #self.create_timer(3, lambda: print(self.reconciler.get_ascii_status()), autostart=True)

        # ----------------------------
        # diagnostics setup
        # ----------------------------

        self.updater = Updater(self)
        self.updater.setHardwareID("hardware_manager")

        # Register a diagnostic checks
        for mc in self.reconciler.controllers:
            self.updater.add(
                f"reconciler-{mc.controller.name}", 
                lambda stat, managed_controller=mc: self.check_reconciler_status(stat, managed_controller))

        for loop in self.looper.get_loops():
            self.updater.add(
                f"loop-{loop.id}",
                lambda stat, l=loop: self.check_loop_status(stat, l)
            )

        self.diagnostic_timer = self.create_timer(1.0, self.updater.update) # update 

        # -------------------------
        # main subscription to input topic
        # -------------------------

        self.sub = self.create_subscription(
            MotionframeArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            5
        )

        self.get_logger().info("Initialized!")

    # ---------------------------
    # Main Reception callback
    # --------------------------

    def motionframe_callback(self, msg: MotionframeArray):
        if not self._is_active: return # skip if node not active

        # create a motion command for each pair, and dispatch them to the queues
        for act_id, val in zip(msg.ids, msg.values):
            #self.get_logger().info(f"{act_id}:{val}")
            self.dispatcher.dispatch(MotionCommand(act_id, val))

    # -----------------------------
    # Diagnostic Tasks
    # -----------------------------

    def check_reconciler_status(self, stat: DiagnosticStatusWrapper, mc: ManagedController):
        status = self.reconciler.get_status_for_controller_json(mc)
        
        if status["goal"] != status["state"]:
            stat.summary(DiagnosticStatus.WARN, "The managed controller is in an unwanted state")
        else:
            stat.summary(DiagnosticStatus.OK, "The managed controller is in the correct state")

        for key, val in flatten_for_diagnostics(status).items():
            stat.add(key, str(val))

        return stat

    # this gets called once per each loop (see __init__)
    def check_loop_status(self, stat: DiagnosticStatusWrapper, loop: LoopDescriptor):
        stat.summary(DiagnosticStatus.OK, f"Status check for loop(id={loop.id}, name={loop.name})")
        status = self.looper.get_loop_status_json(loop)
        del status["ctx_manager"] # these are useless for diagnostics
        del status["exception_cb"]

        # status should be flat
        for key, val in status.items():
            stat.add(key, str(val))

        return stat
    
    # -----------------------------
    # Lifecycle Methods
    # -----------------------------

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
        self._is_active = True # mark flag
        return TransitionCallbackReturn.SUCCESS

    # --- deactivate ---
    def on_deactivate(self, state: State):
        self.get_logger().info("on_deactivate()")

        self.reconciler.set_goal_all(
            ControllerState.INITIALIZED
        )
        self.reconciler.reconcile()
        self._is_active = False
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
        self._is_active = False        
        return TransitionCallbackReturn.SUCCESS

    # --- error ---
    def on_error(self, state: State):
        self.get_logger().info("on_error()")
        return TransitionCallbackReturn.SUCCESS




