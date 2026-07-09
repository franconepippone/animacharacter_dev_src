"""
The supervisor node acts at the top level orchestrator for the entire ros2 system.

Supervisor subscribes to /system_events and /diagnostics; it's also the only node that owns
control over /system_status, which is used to publish global status updates.
An onboard display panel node (or some other signaling tool) can subscribe to /system_status to notify updates.

/system_events mainly catches process crashes/restarts, while /diagnostics catches higher level diagnostic data that
every node publishes. Depending on type and severity, the supervisor may or may not decide to update /system_status to reflect these. 

"""

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.task import Future

from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition, State

from interfaces.msg import SystemEvent, SystemStatus

from diagnostic_updater import Heartbeat

from lifecycle_sup_utility import LifecycleNodeSupervisor, TypedFuture


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

        f1 = self.hwmng_sup.shutdown_async()
        f2 = self.ssmng_sup.shutdown_async()
        
        ok = all([bool(res.success if res else False) for res in (
            self.hwmng_sup.wait_for_future(f1),
            self.ssmng_sup.wait_for_future(f2),
            )
        ])

        msg = SystemStatus()
        msg.status_code = -10 
        msg.note = "some note"
        self.sys_status_pub.publish(msg) # last update before system teardown from the launch system

        # should wait a bit here

        self.context.destroy() # this should kill this node, stop the executor and exit the process

    def on_system_event(self, event: SystemEvent):
        event.proc_name


def main():
    rclpy.init()
    node = Supervisor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()