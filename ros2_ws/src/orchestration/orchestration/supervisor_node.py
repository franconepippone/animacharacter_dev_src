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

from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition, State

from interfaces.msg import SystemEvent, SystemStatus

from diagnostic_updater import Heartbeat

from lifecycle_sup_utility import LifecycleNodeSupervisor


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

        # create all lifecycle supervisors objects for all nodes of the system
        self.hwmng_sup = LifecycleNodeSupervisor(self, '/hardware_manager')

        self.timer = self.create_timer(2.0, self.check_state)

        self.get_logger().info('Master supervisor started')

    def spinup_system(self):
        """Attempts to bring the whole system up"""

    def shutdown_system(self):
        """Attempts to shut down the whole system:
        - shutdown all lifecycle nodes
        - notify /system_status of result
        - shutdown this node (exits the application) -> launch system emits Shutdown()
        """

        ok = all([
            self.hwmng_sup.shutdown(),
            ... # add other operations
        ])

        msg = SystemStatus()
        msg.status_code = -10 
        msg.note = "some note"
        self.sys_status_pub.publish(msg)




def main():
    rclpy.init()
    node = Supervisor(timeout_sec=5.0)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()