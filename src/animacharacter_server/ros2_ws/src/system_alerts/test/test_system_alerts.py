import time
import uuid

from typing import cast, Callable

import pytest
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from rclpy.task import Future

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

    def create_publisher(self, msg_type, topic, qos, callback_group=None):
        publisher = FakePublisher(self, topic)
        self._publishers[topic] = publisher
        return publisher

    def create_subscription(self, msg_type, topic, callback, qos, callback_group=None):
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


def _start_alert_change_waiter(
    executor: SingleThreadedExecutor,
    server: SysAlertsServer,
    timeout: float,
    expected_waiters: int = 1,
) -> Future:
    """Start a waiter and spin until it is subscribed to the next change."""
    future = executor.create_task(server.wait_alert_change(timeout=timeout))

    deadline = time.monotonic() + 1.0
    while len(server._change_waiters) < expected_waiters and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.01)

    assert len(server._change_waiters) == expected_waiters
    return future


def test_wait_alert_change_returns_on_raise():
    """A waiter should resolve when a new alert is raised."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_raise_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        future = _start_alert_change_waiter(executor, server, timeout=2.0)

        alert = Alert(
            level=Level.WARN,
            src="motor",
            code=1,
            brief="hot",
        )

        server.raise_alert(alert)

        executor.spin_until_future_complete(future)

        assert future.result() == (AlertActionType.RAISE, alert)

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_timeout():
    """A waiter should return an empty result when no alert arrives."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("wait_timeout_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        future = executor.create_task(
            server.wait_alert_change(timeout=0.05)
        )

        executor.spin_until_future_complete(future)

        assert future.result() == (None, None)

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_multiple_wait_alert_change_waiters_receive_same_event():
    """All pending waiters should be notified by one alert update."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("multi_wait_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        futures = [
            _start_alert_change_waiter(
                executor,
                server,
                timeout=2.0,
                expected_waiters=index + 1,
            )
            for index in range(100)
        ]

        alert = Alert(
            level=Level.ERR,
            src="driver",
            code=42,
            brief="failure",
        )

        server.raise_alert(alert)

        for future in futures:
            executor.spin_until_future_complete(future)

        results = [future.result() for future in futures]

        assert len(results) == 100
        assert all(
            result == (AlertActionType.RAISE, alert)
            for result in results
        )

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_removes_waiters_after_timeout():
    """Timeout should not leave stale futures in the waiter list."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("wait_cleanup_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        future = executor.create_task(server.wait_alert_change(timeout=0.05))

        executor.spin_until_future_complete(future)

        assert future.result() == (None, None)
        assert server._change_waiters == []

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_rejects_invalid_timeout():
    """A non-positive timeout should fail immediately."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("wait_validation_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        future = executor.create_task(
            server.wait_alert_change(timeout=0)
        )

        with pytest.raises(ValueError):
            executor.spin_until_future_complete(future)

        future = executor.create_task(server.wait_alert_change(timeout=-1))

        with pytest.raises(ValueError):
            executor.spin_until_future_complete(future)

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_clear_event():
    """A waiter should receive clear events as well."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("wait_clear_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        alert = Alert(
            level=Level.ERR,
            src="driver",
            code=100,
            brief="fault",
        )

        server.raise_alert(alert)

        future = _start_alert_change_waiter(executor, server, timeout=2.0)

        server.clear_alert(alert.code)

        executor.spin_until_future_complete(future)

        assert future.result() == (
            AlertActionType.CLEAR,
            Alert(
                level=Level.INFO,
                src="",
                code=alert.code,
            ),
        )

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_cleanup_after_event():
    """A waiter should be removed after receiving an event."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node("wait_event_cleanup_test")
        server = SysAlertsServer(node)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        future = _start_alert_change_waiter(executor, server, timeout=2.0)

        alert = Alert(
            level=Level.INFO,
            src="test",
            code=55,
            brief="ok",
        )

        server.raise_alert(alert)

        executor.spin_until_future_complete(future)

        assert future.result() == (AlertActionType.RAISE, alert)
        assert server._change_waiters == []

    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_does_not_replay_previous_changes():
    """A new waiter should observe only changes published after it subscribes."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_sequential_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        first_alert = Alert(Level.WARN, "motor", 201, brief="first")
        first_waiter = _start_alert_change_waiter(executor, server, timeout=1.0)
        server.raise_alert(first_alert)
        executor.spin_until_future_complete(first_waiter)

        second_alert = Alert(Level.ERR, "driver", 202, brief="second")
        second_waiter = _start_alert_change_waiter(executor, server, timeout=1.0)
        server.raise_alert(second_alert)
        executor.spin_until_future_complete(second_waiter)

        assert first_waiter.result() == (AlertActionType.RAISE, first_alert)
        assert second_waiter.result() == (AlertActionType.RAISE, second_alert)
        assert server._change_waiters == []
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_ignores_identical_raise():
    """An identical raise refreshes TTL but must not resolve a waiter as a change."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_duplicate_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        alert = Alert(Level.WARN, "motor", 203, brief="unchanged")

        server.raise_alert(alert)
        waiter = _start_alert_change_waiter(executor, server, timeout=0.05)
        server.raise_alert(alert)
        executor.spin_until_future_complete(waiter)

        assert waiter.result() == (None, None)
        assert server.get_active_alerts() == {alert.code: alert}
        assert server._change_waiters == []
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_wait_alert_change_receives_ttl_expiry_clear():
    """Expiry should publish a clear event to a waiter subscribed after the raise."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_expiry_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node, expiry_interval=10.0)
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        alert = Alert(Level.WARN, "motor", 204, ttl=0.01, brief="short-lived")

        server.raise_alert(alert)
        waiter = _start_alert_change_waiter(executor, server, timeout=1.0)
        time.sleep(0.02)
        server._expire_alerts()
        executor.spin_until_future_complete(waiter)

        assert waiter.result() == (
            AlertActionType.CLEAR,
            Alert(level=Level.INFO, src="", code=alert.code),
        )
        assert server.get_active_alerts() == {}
        assert server._change_waiters == []
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_timed_out_waiter_is_not_resolved_by_a_later_change():
    """A completed timeout must be removed before a later event is published."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_timeout_race_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        waiter = _start_alert_change_waiter(executor, server, timeout=0.05)
        executor.spin_until_future_complete(waiter)
        server.raise_alert(Alert(Level.WARN, "motor", 205, brief="late"))

        assert waiter.result() == (None, None)
        assert server._change_waiters == []
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def test_cancelled_waiter_is_removed_without_receiving_a_change():
    """Cancelling the internal wait future must release the server registration."""
    if not rclpy.ok():
        rclpy.init(args=[])

    try:
        node = rclpy.create_node(f"wait_cancel_{uuid.uuid4().hex[:8]}")
        server = SysAlertsServer(node)
        executor = SingleThreadedExecutor()
        executor.add_node(node)

        waiter = _start_alert_change_waiter(executor, server, timeout=1.0)
        server._change_waiters[0].cancel()
        executor.spin_until_future_complete(waiter)

        assert waiter.result() == (None, None)
        assert server._change_waiters == []
    finally:
        if rclpy.ok():
            rclpy.shutdown()
