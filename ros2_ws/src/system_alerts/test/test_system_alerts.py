import time
import uuid

from typing import cast, Callable

import pytest
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor

from system_alerts.alert import Alert, AlertActionType, Level
from system_alerts.client import SysAlertsClient
from system_alerts.server import SysAlertsServer


class FakeSubscription:
    def __init__(self, topic, callback):
        self.topic = topic
        self.callback = callback


class FakeTimer:
    def __init__(self, callback):
        self._callback = callback

    def destroy(self):
        return None


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
        self._timers = []

    def create_publisher(self, msg_type, topic, qos):
        publisher = FakePublisher(self, topic)
        self._publishers[topic] = publisher
        return publisher

    def create_subscription(self, msg_type, topic, callback, qos):
        subscription = FakeSubscription(topic, callback)
        self._subscriptions.setdefault(topic, []).append(subscription)
        return subscription

    def create_timer(self, period, callback):
        timer = FakeTimer(callback)
        self._timers.append(timer)
        return timer

    def _deliver(self, topic, message):
        for subscription in self._subscriptions.get(topic, []):
            subscription.callback(message)


def test_client_state_is_updated_from_server_change():
    """A server-side raise should update the client's mirrored state."""
    node = cast(Node, FakeNode())
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    alert = Alert(level=Level.WARN, src="motor", code=7, brief="overtemp")
    server.raise_alert(alert)

    assert client.get_active_alerts()[alert.code] == alert


def test_clear_alert_is_reflected_once_server_publishes_change():
    """A clear action should remove the alert from the client's local mirror."""
    node = cast(Node, FakeNode())
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    alert = Alert(level=Level.ERR, src="driver", code=11, brief="fault")
    server.raise_alert(alert)
    client.clear_alert(alert.code)

    assert alert.code not in client.get_active_alerts()


def test_callbacks_receive_server_updates():
    """Client callbacks should receive every server-published change."""
    node = cast(Node, FakeNode())
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)
    received = []

    client.on_alert_change(lambda action, alert: received.append((action, alert.code)))

    server.raise_alert(Alert(level=Level.INFO, src="session", code=31, brief="ready"))

    assert received == [(AlertActionType.RAISE, 31)]


def test_client_raise_alert_is_processed_by_server_and_mirrored_locally():
    """A client-side raise should be accepted by the server and mirrored back."""
    node = cast(Node, FakeNode())
    client = SysAlertsClient(node)
    server = SysAlertsServer(node)

    client.raise_alert(Level.WARN, "motor", 99, brief="hot")

    assert server.get_active_alerts()[99].code == 99
    assert client.get_active_alerts()[99].code == 99


def _spin_until(
    predicate: Callable,
    timeout: float = 5.0,
    interval: float = 0.1,
    executor: SingleThreadedExecutor | None = None,
) -> None:
    """Wait for a predicate to become true while spinning the ROS executor if provided."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        if executor is not None:
            executor.spin_once(timeout_sec=interval)
        else:
            time.sleep(interval)


def _create_ros_pair(request_topic: str, change_topic: str):
    """Create a server node, a client node, and the alert objects for a ROS test."""
    prefix = f"test_alerts_{uuid.uuid4().hex[:8]}"
    server_node = rclpy.create_node(f"{prefix}_server")
    client_node = rclpy.create_node(f"{prefix}_client")
    server = SysAlertsServer(server_node, request_topic=request_topic, change_topic=change_topic)
    client = SysAlertsClient(client_node, request_topic=request_topic, change_topic=change_topic)
    executor = SingleThreadedExecutor()
    executor.add_node(server_node)
    executor.add_node(client_node)
    return server_node, client_node, server, client, executor


def test_ros2_nodes_propagate_alerts_across_topics():
    """A real ROS 2 client/server pair should propagate a raise event across topics."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        prefix = f"alerts_{uuid.uuid4().hex[:8]}"
        request_topic = f"/{prefix}/requests"
        change_topic = f"/{prefix}/changes"
        _, _, server, client, executor = _create_ros_pair(request_topic, change_topic)

        received_actions: list[tuple[AlertActionType, int]] = []
        client.on_alert_change(lambda action, alert: received_actions.append((action, alert.code)))

        client.raise_alert(Level.WARN, "motor", 123, brief="hot")

        _spin_until(
            lambda: 123 in client.get_active_alerts(),
            timeout=5.0,
            interval=0.1,
            executor=executor,
        )

        assert 123 in client.get_active_alerts()
        assert received_actions == [(AlertActionType.RAISE, 123)]
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_ros2_nodes_propagate_clear_actions():
    """A real ROS 2 clear request should remove the alert from the client's mirror."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        prefix = f"alerts_{uuid.uuid4().hex[:8]}"
        request_topic = f"/{prefix}/requests"
        change_topic = f"/{prefix}/changes"
        _, _, server, client, executor = _create_ros_pair(request_topic, change_topic)

        client.raise_alert(Level.ERR, "driver", 456, brief="fault")
        _spin_until(
            lambda: 456 in client.get_active_alerts(),
            timeout=5.0,
            interval=0.1,
            executor=executor,
        )

        client.clear_alert(456)
        _spin_until(
            lambda: 456 not in client.get_active_alerts(),
            timeout=5.0,
            interval=0.1,
            executor=executor,
        )

        assert 456 not in client.get_active_alerts()
        assert server.get_active_alerts() == {}
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_ros2_nodes_handle_repeated_raise_updates():
    """Repeated raises for the same code should replace the previous alert state."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        prefix = f"alerts_{uuid.uuid4().hex[:8]}"
        request_topic = f"/{prefix}/requests"
        change_topic = f"/{prefix}/changes"
        _, _, server, client, executor = _create_ros_pair(request_topic, change_topic)

        client.raise_alert(Level.WARN, "motor", 789, brief="first")
        _spin_until(
            lambda: 789 in client.get_active_alerts(),
            timeout=5.0,
            interval=0.1,
            executor=executor,
        )

        client.raise_alert(Level.ERR, "motor", 789, brief="second")
        _spin_until(
            lambda: client.get_active_alerts()[789].brief == "second",
            timeout=5.0,
            interval=0.1,
            executor=executor,
        )

        assert client.get_active_alerts()[789].brief == "second"
        assert server.get_active_alerts()[789].brief == "second"
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_server_auto_expires_alerts_when_ttl_is_reached():
    """An alert with an elapsed TTL should be cleared automatically by the server."""
    node = cast(Node, FakeNode())
    client = SysAlertsClient(node)
    server = SysAlertsServer(node, expiry_interval=0.01)

    client.raise_alert(Level.WARN, "motor", 321, ttl=0.01, brief="short")

    deadline = time.time() + 0.5
    while time.time() < deadline:
        server._expire_alerts()
        if 321 not in server.get_active_alerts():
            break
        time.sleep(0.01)

    assert 321 not in server.get_active_alerts()
    assert 321 not in client.get_active_alerts()
