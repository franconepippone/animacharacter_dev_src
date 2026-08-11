from __future__ import annotations

import math
import time
from typing import Callable, Sequence

from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.task import Future
from interfaces.msg import AlertAction

from system_alerts.alert import Alert, AlertActionType, Level
from system_alerts.transport import build_message, decode_action_message

from orchestration.ros_async_utils import wait_future

class SysAlertsServer:
    """Authoritative server that owns the active alert table.

    Clients publish requests to the request topic. The server applies the state
    change, updates its internal table, and republishes the same change on the
    change topic so all clients can mirror it.
    """

    def __init__(
        self,
        host_node: Node,
        request_topic: str = "/system_alerts/requests",
        change_topic: str = "/system_alerts/changes",
        expiry_interval: float = 0.1,
    ) -> None:
        self.node = host_node
        self._request_topic = request_topic
        self._change_topic = change_topic
        self._expiry_interval = max(expiry_interval, 0.001)
        self._active_alerts: dict[int, Alert] = {}
        self._alert_started_at: dict[int, float] = {}
        self._change_callback: Callable[[AlertActionType, Alert], None] | None = None
        self._change_waiters: list[Future] = []

        # prevents race between change and requests
        self.cbg = MutuallyExclusiveCallbackGroup()

        self._publisher = self.node.create_publisher(AlertAction, change_topic, 10, callback_group=self.cbg)
        self._subscription = self.node.create_subscription(
            AlertAction,
            request_topic,
            self._handle_request,
            10,
            callback_group=self.cbg
        )

        self._expiry_timer = self.node.create_timer(self._expiry_interval, self._expire_alerts)

    def raise_alert(self, alert: Alert) -> None:
        """Raise an alert directly on the server and publish the change to clients."""
        self._apply_change(AlertActionType.RAISE, alert)

    def clear_alert(self, code: int) -> None:
        """Clear the alert with the given code and publish the change to clients."""
        self._apply_change(AlertActionType.CLEAR, Alert(level=Level.INFO, src="", code=code))

    def get_active_alerts_table(self) -> dict[int, Alert]:
        """Return a copy of the server-authoritative active-alert table."""
        return dict(self._active_alerts)
    
    def get_active_alerts(self) -> tuple[Alert, ...]:
        """Returns a tuple of all the currently active alerts"""
        return tuple(self._active_alerts.values())
    
    def is_alert_active(self, alert_id: int):
        return alert_id in self._active_alerts

    def on_alert_change(self, callback: Callable[[AlertActionType, Alert], None]) -> None:
        """Register a callback invoked for every server-published alert change."""
        self._change_callback = callback
    
    def get_alerts_from_level(self, starting_level: int) -> tuple[Alert, ...]:
        """Returns all the active alerts of level above or equal to the one specified"""
        return tuple([alert for alert in self._active_alerts.values() 
                      if alert.level >= starting_level])

    async def wait_alert_change(
        self,
        timeout: float,
    ) -> tuple[AlertActionType, Alert] | tuple[None, None]:
        future: Future[tuple[AlertActionType, Alert]] = Future()
        self._change_waiters.append(future)

        try:
            result = await wait_future(
                self.node,
                future,
                timeout,
                self.cbg,
            )

            if result is None:
                return (None, None)

            return result

        finally:
            self._change_waiters.remove(future)


    def _apply_change(self, action: AlertActionType, alert: Alert) -> bool:
        """Apply an alert state change.

        Returns:
            True if a change was published.
        """
        if action is AlertActionType.RAISE:
            current = self._active_alerts.get(alert.code)

            # Always refresh the lifetime.
            self._active_alerts[alert.code] = alert
            self._alert_started_at[alert.code] = time.monotonic()

            # Don't republish if nothing except the expiry changed.
            if current == alert:
                return False

        elif action is AlertActionType.CLEAR:
            if alert.code not in self._active_alerts:
                return False

            self._active_alerts.pop(alert.code)
            self._alert_started_at.pop(alert.code, None)

        else:
            raise ValueError(f"Unsupported alert action: {action}")

        self._publish_change(action, alert)

        if self._change_callback:
            self._change_callback(action, alert)

        # Notify all pending waiters.
        for future in self._change_waiters[:]:
            if not future.done():
                future.set_result((action, alert))

        return True
                
    def _handle_request(self, message: AlertAction) -> None:
        action, alert = decode_action_message(message)
        self._apply_change(action, alert)

    def _publish_change(self, action: AlertActionType, alert: Alert) -> None:
        self._publisher.publish(build_message(action, alert))

    def _expire_alerts(self) -> None:
        now = time.monotonic()
        expired_alerts = [
            alert
            for code, alert in self._active_alerts.items()
            if alert.ttl != math.inf
            and code in self._alert_started_at
            and now - self._alert_started_at[code] >= alert.ttl
        ]

        for alert in expired_alerts:
            self._apply_change(
                AlertActionType.CLEAR,
                alert,
            )