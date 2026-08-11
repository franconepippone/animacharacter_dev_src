"""
Contains utility components to allow nodes to listen / produce heartbeats.
"""

from typing import Callable
import time
from dataclasses import dataclass

from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from interfaces.msg import Heartbeat


class HeartbeatGenerator:
    """Simple heartbeat generator. Create during __init__ of a node, pass 'self' as an argument and the 
    node will automatically publish heartbeats while spinning that can be received by a HeartbeatListener.

    If name is left empty, uses host_node's name.
    """

    def __init__(self, 
            host_node: Node, 
            period: float, 
            tolerance: float,
            name: str = '', 
            hb_topic: str = "/heartbeats"
        ) -> None:
        self.host_node: Node = host_node
        self.name = name or host_node.get_name()
        self.logger = host_node.get_logger().get_child(f'hb_{self.name}')
        self.hb_topic = hb_topic

        # we send a hb and we say the next hb is expected to arrive within this time window;
        # period is always smaller than this by 'tolerance' amount. This ensures the hb listener
        # has a big enough time margin in case hb does not arrive on time
        assert period > 0 and tolerance > 0
        self.hb_time_window = float(period + tolerance)

        cbg = MutuallyExclusiveCallbackGroup()
        self.hb_pub = host_node.create_publisher(
            Heartbeat,
            self.hb_topic,
            10,
            callback_group=cbg # ensure this does not interfere with node's other callbacks
        )

        self.timer = host_node.create_timer(period, self._send_hb)

    def _send_hb(self):
        hb = Heartbeat()
        hb.name = self.name
        hb.next_within = self.hb_time_window
        self.hb_pub.publish(hb)

@dataclass(slots=True)
class HbEntry:
    deadline: float
    reported: bool

class HeartbeatListener:
    """Monitor heartbeats published by HeartbeatGenerator instances. Heartbeats received dynamically populate
    the internal table. If a heartbeat times out, the provided on_timeout callback is invoked. 
    
    HB publishing period and timeout specifics are defined by each hb generator."""

    def __init__(
        self,
        host_node: Node,
        on_timeout: Callable[[str], None],
        hb_topic: str = "/heartbeats",
        check_period: float = 1.0,
    ) -> None:
        self.host_node = host_node
        self.on_timeout = on_timeout
        self.hb_topic = hb_topic

        self.logger = host_node.get_logger().get_child("heartbeat_listener")

        # name -> HbEntry
        self.heartbeats: dict[str, HbEntry] = {}

        cbg = MutuallyExclusiveCallbackGroup()

        self.hb_sub = host_node.create_subscription(
            Heartbeat,
            self.hb_topic,
            self._heartbeat_received,
            10,
            callback_group=cbg,
        )

        self.timer = host_node.create_timer(
            check_period,
            self._check_heartbeats,
            callback_group=cbg,
        )

    def _heartbeat_received(self, hb: Heartbeat) -> None:
        now = time.monotonic()
        if not hb.name in self.heartbeats:
            self.logger.info(f"New heartbeat registered: {hb.name}") 
        self.heartbeats[hb.name] = HbEntry(
            deadline=now + hb.next_within, 
            reported=False
        )

    def _check_heartbeats(self) -> None:
        now = time.monotonic()

        for name, heartbeat in self.heartbeats.items():
            if (
                not heartbeat.reported
                and now > heartbeat.deadline
            ):
                heartbeat.reported = True
                self.logger.warning(f"Heartbeat timeout: {name}")
                self.on_timeout(name)