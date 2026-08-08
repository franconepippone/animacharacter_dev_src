from __future__ import annotations

import math
from typing import Callable

from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from interfaces.msg import AlertAction

from system_alerts.alert import Alert, AlertActionType, Level
from system_alerts.transport import decode_action_message, build_message


class SysAlertsClient:
    """Client-side mirror of the server-authoritative alert state.

    The client does not mutate its local state directly when an alert is raised.
    Instead, it sends requests to the server and updates its local table only from
    server-published change messages.
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

        # prevents race between change and requests
        cbg = MutuallyExclusiveCallbackGroup()
        
        self._publisher = self.node.create_publisher(AlertAction, request_topic, 10, callback_group=cbg)
        self._subscription = self.node.create_subscription(
            AlertAction,
            change_topic,
            self._handle_change,
            10,
            callback_group=cbg
        )

    def raise_alert(
        self,
        level: int,
        code: int,
        src: str,
        ttl: float = math.inf,
        subcode: int = -1,
        brief: str = "",
        description: str = "",
    ) -> None:
        """Send a raise request to the server for a new alert."""
        alert = Alert(
            level=level,
            src=src,
            code=code,
            ttl=0.0 if level == Level.INFO else ttl,
            subcode=subcode,
            brief=brief,
            description=description,
        )
        self._publish_action(AlertActionType.RAISE, alert)

    def clear_alert(self, code: int) -> None:
        """Send a clear request to the server for the alert identified by code."""
        self._publish_action(AlertActionType.CLEAR, Alert(level=Level.INFO, src="", code=code))

    def get_active_alerts(self) -> dict[int, Alert]:
        """Return a copy of the locally mirrored active-alert table."""
        return dict(self._active_alerts)

    def on_alert_change(self, callback: Callable[[AlertActionType, Alert], None]) -> None:
        """Register a callback invoked for every server-published alert change."""
        self._change_callback = callback

    def _publish_action(self, action: AlertActionType, alert: Alert) -> None:
        self._publisher.publish(build_message(action, alert))

    def _handle_change(self, message: AlertAction) -> None:
        action, alert = decode_action_message(message)
        if action is AlertActionType.RAISE:
            self._active_alerts[alert.code] = alert
        elif action is AlertActionType.CLEAR:
            self._active_alerts.pop(alert.code, None)

        if self._change_callback:
            self._change_callback(action, alert)