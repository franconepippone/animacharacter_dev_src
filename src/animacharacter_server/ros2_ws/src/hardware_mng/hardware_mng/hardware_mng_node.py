import json
import time

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from interfaces.msg import MotionframeArray
from std_msgs.msg import String

from diagnostic_updater import Updater
from diagnostic_updater import DiagnosticStatusWrapper, DiagnosticStatus

from .dispatcher import Dispatcher
from .looper import LoopSupervisor, display_status_from_json, LoopDescriptor, Signal
from .abstract_hw_controller import MotionCommand, BaseHardwareController
from .databus import Databus
from .hw_controller_state_reconciler import (
    HWControllerStateReconciler,
    ControllerState,
    ManagedController
)
from system_alerts import SysAlertsClient, Level
from .utils import flatten_for_diagnostics
from system_commons import exit_codes as xc
from system_commons import alert_codes as ac
from .signals_definitions import (
    SIG_CONTOLLER_WARNING,
    SIG_CONTROLLER_ERROR,
    SIG_CONTROLLER_FATAL,
    SIG_CONTROLLER_GENERIC_EXCEPTION
)



# of type MotionframeArray
INPUT_TOPIC = 'input_motionframes'
CONFIG_TOPIC = 'config_update'

class HardwareManagerNode(LifecycleNode):
    def __init__(self, 
            dispatcher: Dispatcher, 
            looper: LoopSupervisor, 
            loop_controllers_pairs: list[tuple[LoopDescriptor, BaseHardwareController]],
            databus: Databus
        ):
        super().__init__('hardware_manager')
        self.dispatcher: Dispatcher = dispatcher
        self.looper = looper
        self.loop_controllers_pairs = loop_controllers_pairs # loop and controller are always kept together in a tuple
        self.loaded_hw_controllers = [t[1] for t in loop_controllers_pairs]
        self._is_active = False
        self._shutdown_requested = False
        self._controller_databus = databus # we dont really need it, but we keep track of it just in case.

        # ------------------------
        # Controller state automatic reconciliation
        # -----------------------

        # setting up reconciler for background state reconciliation of controller state
        # (if a controller fails to update its state during a lifecycle transistion, this will try to recoincile in the background)
        self.reconciler = HWControllerStateReconciler(
            self.handle_loop_signal, # NOTE abuse of this cb method...
            looper=self.looper,
            logger=self.get_logger().get_child('reconciler'),
        )

        for loop, ctrl in loop_controllers_pairs:
            self.reconciler.add_controller(loop, ctrl)
            loop.signal_handler = lambda s: self.handle_loop_signal(ctrl, loop, s)

        self.reconcile_timer = self.create_timer(3, self.reconciler.reconcile, autostart=True)
        
        #self.create_timer(3, lambda: print(self.reconciler.get_ascii_status()), autostart=True)

        # ----------------------------
        # diagnostics setup
        # ----------------------------

        self.updater = Updater(self)
        self.updater.setHardwareID("hardware_manager")

        self.looper.stop_all()

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
        # main subscription to input topic and configs
        # -------------------------

        self.sub = self.create_subscription(
            MotionframeArray,
            INPUT_TOPIC,
            self.motionframe_callback,
            5
        )

        self.sub_config = self.create_subscription(
            String,
            CONFIG_TOPIC,
            self.update_config_callback,
            5
        )

        # ----------------------------
        # set up alert client
        # ----------------------------
        self.alert_cli = SysAlertsClient(self)

        self.get_logger().info("Initialized!")

    # ---------------------------
    # Main callbacks
    # --------------------------

    def handle_loop_signal(self, ctrl: BaseHardwareController, loop: LoopDescriptor, signal: Signal):
        self.get_logger().info(f"Received signal {signal} from loop: {loop.name} [controller {ctrl.name}].")

        if signal.name == SIG_CONTROLLER_FATAL:
            if self._shutdown_requested:
                return

            self.alert_cli.raise_alert(
                Level.FATAL,
                ac.FTL_HW_CONTROLLER_FATAL,
                self.get_name(),
                subcode=signal.kwargs.get("code", 0),
                brief=f"Fatal error in controller '{ctrl.name}'",
                description=signal.kwargs.get("note", "no further description available")
            )

            self._shutdown_requested = True
            self.get_logger().warning(f"Received global shutdown signal from for controller: {ctrl.name}")
            self._is_active = False

            self.looper.stop_all(block=True, timeout=1.0)
            self.reconciler.set_goal_all(ControllerState.UNINITIALIZED)
            self.reconciler.reconcile()

            time.sleep(.5)

            # immediate system exit
            raise SystemExit(xc.HWMNG_CONTROLLER_FATAL)

        elif signal.name == SIG_CONTROLLER_ERROR:
            # Publish to diagnostics
            pass

        elif signal.name == SIG_CONTOLLER_WARNING:
            # publish to diagnostics
            pass

        elif signal.name == SIG_CONTROLLER_GENERIC_EXCEPTION:
            pass
        
        else:
            self.get_logger().info(f"Unhandled loop signal: {signal}")
            return

        

    def update_config_callback(self, msg: String):
        # WE MIGHT REMOVE THIS, CONFIGS ARE ALREADY QUEUED AUTOMATICALLY
        if not self._is_active: return # skip if node not active

        if not isinstance(msg.data, str):
            self.get_logger().warning(f"Message received from config topic was not a string, but was of type: {type(msg.data)}")
            return

        try:
            configs = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().warning(f"Failed to parse config json -> {e}")
            return
        
        # updates all controllers with configs (calls subscribed handlers)
        for ctrl in self.loaded_hw_controllers:
            ctrl._queue_config_update(configs)

            
    def motionframe_callback(self, msg: MotionframeArray):
        if not self._is_active: return # skip if node not active

        # create a motion command for each pair, and dispatch them to the queues
        for act_id, val in zip(msg.ids, msg.values):
            #self.get_logger().info(f"{act_id}:{val}")
            dispatcher_cmd = (act_id, MotionCommand(act_id, val)) # we do this to use the entire MotionCommand as payload
            self.dispatcher.dispatch(dispatcher_cmd)

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
        # TODO this should reconcile until all controllers have been deactivated
        self.reconciler.reconcile()
        self._is_active = False        
        return TransitionCallbackReturn.SUCCESS

    # --- error ---
    def on_error(self, state: State):
        self.get_logger().info("on_error()")
        return TransitionCallbackReturn.SUCCESS




