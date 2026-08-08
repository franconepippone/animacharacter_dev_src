"""
The supervisor node acts at the top level orchestrator for the entire ros2 system.

Supervisor subscribes to /process_events and monitors alerts; it's also the only node that owns
control over /system_status, which is used to publish global status updates.
An onboard display panel node (or some other signaling tool) can subscribe to /system_status to notify updates.

/process_events mainly catches process crashes/restarts, while alerts catches higher level events that
every node emits. Based on these events, the supervisor updates a local FSM model of the system, and publishes updates to /system_status. 

"""
from typing import Callable, Any, cast
import time

import rclpy
from rclpy.timer import Timer
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from interfaces.msg import ProcessEvent, SystemStatus
from system_commons import exit_codes as xc
from system_commons import alert_codes as ac

from system_alerts.system_alerts import SysAlertsServer, Level, Alert, AlertActionType
from system_alerts.system_alerts.alert import empty_alert
from system_alerts.system_alerts.transport import to_ros_alert, from_ros_alert

from .lifecycle_sup_utility import LifecycleNodeSupervisor
from .launch_utils import SysEventType
from . import proc_names as pn
from .ros_async_utils import BetterAsyncNode
from .state_machine.system_fsm import SystemFSM, SystemState

PROCESS_EVENTS_TOPIC = "/process_events"
SYSTEM_STATUS_TOPIC = "/system_status"


SHUTDOWN_POSTPONE_TIME = 1.0 #seconds



class Supervisor(BetterAsyncNode):
    def __init__(self):
        super().__init__("supervisor")

        self.rcbg = ReentrantCallbackGroup()
        self.one_shot_cbg = MutuallyExclusiveCallbackGroup() # constraints one-shot-timers callbacks to be mutually-exclusive (makes shutdown m-e)

        # hook for all system-level events produced by the launch systems (process start / exit / crash)
        self.sysevents_sub = self.create_subscription(
            ProcessEvent,
            PROCESS_EVENTS_TOPIC,
            self.on_process_event_cb,
            5
        )

        # emits status update events on this topic; UI (monitor panel) nodes can subscribe to this to notify user of current system state
        self.sys_status_pub = self.create_publisher(
            SystemStatus,
            SYSTEM_STATUS_TOPIC,
            5
        )

        # create all lifecycle supervisors components for all lifecycle nodes of the system
        self.hwmng_sup = LifecycleNodeSupervisor(self, '/hardware_manager')
        self.ssmng_sup = LifecycleNodeSupervisor(self, '/session_manager')

        # -----------------
        # Host Alert server
        self.alert_server = SysAlertsServer(self)
        self.alert_server.on_alert_change(self.on_alert_change_cb)


        # -----------------
        # System State machine rapresentation
        self.fsm = SystemFSM(self.alert_server) 

        def imalive(): 
            self.get_logger().info("imalive")

        #self.create_timer(.5, imalive)

        self.create_one_shot_timer(0.0, self.startup_routine)

        self.get_logger().info('Master supervisor instantiated.')

    ### ============================
    ### UTILITY METHODS
    ### ============================

    def publish_system_status(self):
        """Grabs status from FSM and publishes it to /system_status"""
        msg = SystemStatus()
        msg.state_id = self.fsm.state.value
        msg.is_degraded = self.fsm.degraded
        msg.fault_ref = to_ros_alert(self.fsm.fault_ref_alert if self.fsm.fault_ref_alert is not None else empty_alert()) 

        self.sys_status_pub.publish(msg)

    ### ============================
    ### SYSTEM LIFECYCLE MANAGEMENT
    ### ============================
    
    async def startup_routine(self):
        """Routine executed as soon as the node enters the executor loop"""

        self.get_logger().info('Master supervisor entered executor.')

        ok = await self.spinup_system()
        if not ok:
            # move fsm to fault
            await self.shutdown_system()
            return

        self.fsm.change_state(SystemState.STANDBY)

        
          #  <--- CINTINUE FRO MHERE

          # eventaully move fsm to STDBY



    async def spinup_system(self) -> bool:
        """Attempts to bring the whole system up"""

        self.hwmng_sup.timeout = 3
        if not self.hwmng_sup.configure():
            # activation of hwmng is done by sessmng node
            self.get_logger().warning("Could not configure hardware manager node, aborting spinup.")
            return False
        
        if not self.ssmng_sup.configure():
            self.get_logger().warning("Could not configure session manager node, aborting spinup.")
            return False

        if not self.ssmng_sup.activate():
            self.get_logger().warning("Could not activate session manager node, aborting spinup.")
            return False

        return True
    
        ### READY SYSTEM WIP
        
        waiting_for = {"hardware_manager", "session_manager"}

        def is_ready(alert: Alert) -> bool:
            return (
                alert.level == Level.INFO
                and alert.brief.upper() == "READY"
                and alert.src.lstrip("/") in waiting_for
            )

        for alert in self.alert_server.get_active_alerts().values():
            if is_ready(alert):
                waiting_for.discard(alert.src.lstrip("/"))

        deadline = time.monotonic() + 10.0
        while waiting_for:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.get_logger().warning(
                    f"Timed out waiting for READY from: {', '.join(sorted(waiting_for))}."
                )
                return False

            action, alert = await self.alert_server.wait_alert_change(remaining)
            if action is AlertActionType.RAISE and alert is not None and is_ready(alert):
                waiting_for.discard(alert.src.lstrip("/"))
            

        return True

    async def shutdown_system(self):
        """Attempts to shut down the whole system:
        - shutdown all lifecycle nodes
        - notify /system_status of result
        - shutdown this node (exits the application) -> launch system emits Shutdown()
        """
        

        self.get_logger().warning('System shutdown initiated.')

        results = await self.agather(
                    self.hwmng_sup.shutdown(),
                    self.ssmng_sup.shutdown()
                )

        ok = all(results)

        self.get_logger().warning(f'Lifecycle nodes all shutdown: {ok}.')

        legal = self.fsm.force_change_state(SystemState.SHUTDOWN)

        self.get_logger().warning(f'Finalizing shutdown, exiting process.')

        await self.asleep(1.0)

        rclpy.shutdown() # this releases executor.spin and exits process

    ### ============================
    ### CALLBACKS
    ### ============================

    def on_alert_change_cb(self, action: AlertActionType, alert: Alert):
        """ Main trigger for updating the system state and FSM based on alerts. All system events (i.e. process events) are redirected to some kind
        of alerts, meaning that this is the one and only entry point for updating the system state machine. 
        """

        result = self.fsm.update_state(action, alert)
        if result.changed:
            self.publish_system_status() # publish on topic

            if not result.legal_transition:
                self.get_logger().warning(f"Illegal state change forced from {result.prev_state.name} to {result.new_state.name}.")
            else:
                self.get_logger().info(f"System state changed from {result.prev_state.name} to {result.new_state.name}.")


        if self.fsm.state == SystemState.FAULT:
            self.get_logger().error("System transitioned to FAULT state, scheduling shutdown.")
            self.create_one_shot_timer(0.5, self.shutdown_system)

    

    def on_process_event_cb(self, event: ProcessEvent):
        # this is sketch code, needs testing

        evt_type = SysEventType(event.event_type)

        self.get_logger().info(f"Got process event: {event}")

        """
        We listen for process events and redirect them to the alert system. If a core process crashes, 
        a FATAL alert is raised and shutdown is initiated.
        
        """

        if pn.get_domain_from_proc_name(event.proc_name) == pn.DOMAIN_CORE:
            
            if evt_type in (SysEventType.EXIT, SysEventType.CRASH) :
                action = 'crashed' if evt_type == SysEventType.CRASH else 'exited'
                exit_cause = xc.get_cause(event.exit_code)

                self.get_logger().warning(f"The core process \"{event.proc_name}\" has {action} with code: {event.exit_code}, "
                        f"Raising FATAL alert: {exit_cause}")

                # turn this process event into an alert
                ftl_alert = Alert(
                    level=Level.FATAL,
                    src = event.proc_name or "unknown-process",
                    code = ac.FTL_CORE_PROC_CRASH,
                    subcode = event.exit_code, # keep the original process exit code
                    brief=f"Core process {action}",
                    description=f"The core process \"{event.proc_name}\" has crashed with code: {event.exit_code}.\nCause: {exit_cause if exit_cause else 'unknown'}",
                )
                self.alert_server.raise_alert(ftl_alert)

        # non critical event
        else:
            if evt_type == SysEventType.START:
                pass
                # implement restart counter
            






def main(args=None):
    rclpy.init(args=args)

    node = Supervisor()
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    executor.spin()

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    
    exit(0) # if we reach this point, then this shutdown was intentional
