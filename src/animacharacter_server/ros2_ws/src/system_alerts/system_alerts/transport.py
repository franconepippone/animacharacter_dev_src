from __future__ import annotations

from interfaces.msg import Alert as MsgAlert
from interfaces.msg import AlertAction

from system_alerts.alert import Alert, AlertActionType, Level


def to_ros_alert(alert: Alert) -> MsgAlert:
    """Convert the application-level alert model into the ROS message type."""
    ros_alert = MsgAlert()
    ros_alert.level = int(alert.level)
    ros_alert.src = str(alert.src)
    ros_alert.code = int(alert.code)
    ros_alert.ttl = float(alert.ttl)
    ros_alert.subcode = int(alert.subcode)
    ros_alert.brief = str(alert.brief)
    ros_alert.description = str(alert.description)
    return ros_alert


def from_ros_alert(message: MsgAlert) -> Alert:
    """Convert a ROS alert message back into the application-level alert model."""
    return Alert(
        level=int(message.level),
        src=str(message.src),
        code=int(message.code),
        ttl=float(message.ttl),
        subcode=int(message.subcode),
        brief=str(message.brief),
        description=str(message.description),
    )


def build_message(action: AlertActionType, alert: Alert) -> AlertAction:
    message = AlertAction()
    message.action = action.value
    message.alert = to_ros_alert(alert)
    return message

def decode_action_message(message: AlertAction) -> tuple[AlertActionType, Alert]:
    action = AlertActionType(message.action)
    return action, from_ros_alert(message.alert)