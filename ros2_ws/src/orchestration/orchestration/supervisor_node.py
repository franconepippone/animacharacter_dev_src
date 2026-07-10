"""
The supervisor node acts at the top level orchestrator for the entire ros2 system.

Supervisor subscribes to /system_events and /diagnostics; it's also the only node that owns
control over /system_status, which is used to publish global status updates.
An onboard display panel node (or some other signaling tool) can subscribe to /system_status to notify updates.

/system_events mainly catches process crashes/restarts, while /diagnostics catches higher level diagnostic data that
every node publishes. Depending on type and severity, the supervisor may or may not decide to update /system_status to reflect these. 

"""
import time

import rclpy
from rclpy.node import Node
from interfaces.msg import SystemEvent, SystemStatus

from .lifecycle_sup_utility import LifecycleNodeSupervisor
from .launch_utils import SysEventType
from . import proc_names as pn



SYSTEM_EVENTS_TOPIC = "/system_events"
SYSTEM_STATUS_TOPIC = "/system_status"

class Supervisor(Node):
    def __init__(self):
        super().__init__("supervisor")

        # hook for all system-level events produced by the launch systems (process start / exit / crash)
        self.sysevents_sub = self.create_subscription(
            SystemEvent,
            SYSTEM_EVENTS_TOPIC,
            self.on_system_event,
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

        self.get_logger().info('Master supervisor started')

    def spinup_system(self):
        """Attempts to bring the whole system up"""

        self.hwmng_sup.timeout = 3
        if not self.hwmng_sup.configure():
            # activation of hwmng is done by sessmng node
            self.get_logger().warning("Could not configure hardware manager node, aborting spinup.")
            self.shutdown_system()
            return
        
        if not self.ssmng_sup.configure():
            self.get_logger().warning("Could not configure session manager node, aborting spinup.")
            self.shutdown_system()
            return

        if not self.ssmng_sup.activate():
            self.get_logger().warning("Could not activate session manager node, aborting spinup.")
            self.shutdown_system()
            return

    def shutdown_system(self):
        """Attempts to shut down the whole system:
        - shutdown all lifecycle nodes
        - notify /system_status of result
        - shutdown this node (exits the application) -> launch system emits Shutdown()
        """
        

        self.get_logger().warning('System shutdown initiated.')

        f1 = self.hwmng_sup.shutdown_async()
        f2 = self.ssmng_sup.shutdown_async()
        
        ok = all([bool(res.success if res else False) for res in (
            self.hwmng_sup.wait_for_future(f1, 1.0),
            self.ssmng_sup.wait_for_future(f2, 1.0),
            )
        ])

        self.get_logger().warning(f'Lifecycle nodes shutdown: {ok}.')

        msg = SystemStatus()
        msg.status_code = -10 
        msg.note = "some note"
        self.sys_status_pub.publish(msg) # last update before system teardown from the launch system

        #time.sleep(1)
        # should wait a bit here

        self.get_logger().warning(f'Finalizing shutdown.')
        #raise SystemExit # exit the process, launch will react

    def on_system_event(self, event: SystemEvent):
        # this is sketch code, needs testing

        evt_type = SysEventType(event.event_type)

        if pn.get_domain_from_proc_name(event.proc_name) == pn.DOMAIN_CORE:
            
            if evt_type in (SysEventType.EXIT, SysEventType.CRASH) :
                
                self.get_logger().error(f"A core process has exited: {event.proc_name}")
                
                self.create_timer(5.0, self.shutdown_system)
                return
                


def main():
    rclpy.init()
    node = Supervisor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()