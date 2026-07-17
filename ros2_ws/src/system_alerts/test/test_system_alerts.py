import time
import uuid

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor

from system_alerts.alert import Alert, AlertActionType, Level
from system_alerts.client import SysAlertsClient
from system_alerts.server import SysAlertsServer


class FakeSubscription:
    def __init__(self, topic, callback):
        self.topic = topic
        self.callback = callback


class FakePublisher:
    def __init__(self, node, topic):
        self._node = node
        self.topic = topic

    def publish(self, message):
        self._node._deliver(self.topic, message)


class FakeNode:
    def __init__(self):
        self._subscriptions = {}
        self._publishers = {}

    def create_publisher(self, msg_type, topic, qos):
        publisher = FakePublisher(self, topic)
        self._publishers[topic] = publisher
        return publisher

    def create_subscription(self, msg_type, topic, callback, qos):
        subscription = FakeSubscription(topic, callback)
        self._subscriptions.setdefault(topic, []).append(subscription)
        return subscription

    def _deliver(self, topic, message):
        for subscription in self._subscriptions.get(topic, []):
            subscription.callback(message)


def test_client_state_is_updated_from_server_change():
    node = FakeNode()
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    alert = Alert(level=Level.WARN, src="motor", code=7, brief="overtemp")
    server.raise_alert(alert)

    assert client.get_active_alerts()[alert.code] == alert


def test_clear_alert_is_reflected_once_server_publishes_change():
    node = FakeNode()
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    alert = Alert(level=Level.ERR, src="driver", code=11, brief="fault")
    server.raise_alert(alert)
    client.clear_alert(alert.code)

    assert alert.code not in client.get_active_alerts()


def test_callbacks_receive_server_updates():
    node = FakeNode()
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)
    received = []

    client.on_alert_change(lambda action, alert: received.append((action, alert.code)))

    server.raise_alert(Alert(level=Level.INFO, src="session", code=31, brief="ready"))

    assert received == [(AlertActionType.RAISE, 31)]


def test_client_raise_alert_is_processed_by_server_and_mirrored_locally():
    node = FakeNode()
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    client.raise_alert(Level.WARN, "motor", 99, brief="hot")

    assert server.get_active_alerts()[99].code == 99
    assert client.get_active_alerts()[99].code == 99


def test_ros2_nodes_propagate_alerts_across_topics():
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        base_name = f"test_system_alerts_{uuid.uuid4().hex[:8]}"
        request_topic = f"/{base_name}/requests"
        change_topic = f"/{base_name}/changes"

        server_node = rclpy.create_node(f"{base_name}_server")
        client_node = rclpy.create_node(f"{base_name}_client")
        server = SysAlertsServer(server_node, request_topic=request_topic, change_topic=change_topic)
        client = SysAlertsClient(client_node, request_topic=request_topic, change_topic=change_topic)

        executor = SingleThreadedExecutor()
        executor.add_node(server_node)
        executor.add_node(client_node)

        received_actions: list[tuple[AlertActionType, int]] = []
        client.on_alert_change(lambda action, alert: received_actions.append((action, alert.code)))

        client.raise_alert(Level.WARN, "motor", 123, brief="hot")

        deadline = time.time() + 5.0
        while time.time() < deadline:
            executor.spin_once(timeout_sec=0.1)
            if 123 in client.get_active_alerts():
                break

        assert 123 in client.get_active_alerts()
        assert received_actions == [(AlertActionType.RAISE, 123)]
    finally:
        if rclpy.ok():
            rclpy.shutdown()
