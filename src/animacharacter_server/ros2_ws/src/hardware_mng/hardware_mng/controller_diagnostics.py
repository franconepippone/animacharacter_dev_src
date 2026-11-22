from __future__ import annotations

from diagnostic_msgs.msg import DiagnosticStatus
from diagnostic_updater import DiagnosticStatusWrapper
from lifecycle_pkg.events import LifecycleEvent, State as ControllerState


def make_controller_status(
    status: DiagnosticStatusWrapper,
    controller_name: str,
    live_state: ControllerState,
    target_state: ControllerState,
    last_event: LifecycleEvent | None,
) -> DiagnosticStatusWrapper:
    """Populate a diagnostic status with one controller's current situation."""
    if live_state == ControllerState.FAULTED:
        status.summary(
            DiagnosticStatus.ERROR,
            f'Controller {controller_name} is faulted',
        )
    elif live_state != target_state:
        status.summary(
            DiagnosticStatus.WARN,
            f'Controller {controller_name} is transitioning',
        )
    else:
        status.summary(
            DiagnosticStatus.OK,
            f'Controller {controller_name} is {live_state.name}',
        )

    status.add('live_state', live_state.name)
    status.add('target_state', target_state.name)
    if last_event is not None:
        status.add('last_event', last_event.message or type(last_event).__name__)
    return status
