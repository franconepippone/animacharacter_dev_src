from __future__ import annotations

import math
from typing import Callable

from rclpy.node import Node
from interfaces.msg import Alert as MsgAlert
from interfaces.msg import AlertAction

from system_alerts.alert import Alert, AlertActionType, Level
from system_alerts.transport import decode_action_message, build_message


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
    ) -> None:
        self.node = host_node
        self._request_topic = request_topic
        self._change_topic = change_topic
        self._active_alerts: dict[int, Alert] = {}
        self._change_callback: Callable[[AlertActionType, Alert], None] | None = None

        self._publisher = self.node.create_publisher(AlertAction, change_topic, 10)
        self._subscription = self.node.create_subscription(
            AlertAction,
            request_topic,
            self._handle_request,
            10,
        )

    def raise_alert(self, alert: Alert) -> None:
        """Raise an alert directly on the server and publish the change to clients."""
        self._apply_change(AlertActionType.RAISE, alert)

    def clear_alert(self, code: int) -> None:
        """Clear the alert with the given code and publish the change to clients."""
        self._apply_change(AlertActionType.CLEAR, Alert(level=Level.INFO, src="", code=code))

    def get_active_alerts(self) -> dict[int, Alert]:
        """Return a copy of the server-authoritative active-alert table."""
        return dict(self._active_alerts)

    def on_alert_change(self, callback: Callable[[AlertActionType, Alert], None]) -> None:
        """Register a callback invoked for every server-published alert change."""
        self._change_callback = callback

    def _handle_request(self, message: AlertAction) -> None:
        action, alert = decode_action_message(message)
        self._apply_change(action, alert)

    def _apply_change(self, action: AlertActionType, alert: Alert) -> None:
        if action is AlertActionType.RAISE:
            self._active_alerts[alert.code] = alert
        elif action is AlertActionType.CLEAR:
            self._active_alerts.pop(alert.code, None)
        else:
            raise ValueError(f"Unsupported alert action: {action}")

        self._publish_change(action, alert)

        if self._change_callback:
            self._change_callback(action, alert)

    def _publish_change(self, action: AlertActionType, alert: Alert) -> None:
        self._publisher.publish(build_message(action, alert))
