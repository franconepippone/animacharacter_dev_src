from __future__ import annotations

import json
import threading
import time
from queue import Empty, SimpleQueue

from diagnostic_msgs.msg import DiagnosticStatus
from diagnostic_updater import DiagnosticStatusWrapper, Updater
from interfaces.msg import MotionframeArray
from lifecycle_pkg.events import (
    FanOutEventSink,
    LifecycleEvent,
    State as ControllerState,
)
from lifecycle_pkg import LifecycleRunner
from rclpy.lifecycle import (
    LifecycleNode,
    State as RosLifecycleState,
    TransitionCallbackReturn,
)
from rclpy.parameter import Parameter
from std_msgs.msg import String

from orchestration.heartbeats import HeartbeatGenerator
from system_commons import proc_names as process_names

from .abstract_hw_controller import BaseHardwareController, MotionCommand
from .databus import Databus, DatabusError
from .dispatcher import Dispatcher
from .event_sinks import ControllerEventSink, RcutilsEventSink
from .plugins_loader import PluginLoadIssue, load_controllers


INPUT_TOPIC = "input_motionframes"
CONFIG_TOPIC = "config_update"


class HardwareManagerNode(LifecycleNode):
    """Load hardware plugins and coordinate their lifecycle runners."""

    def __init__(self) -> None:
        super().__init__("hardware_manager")
        self.declare_parameter(
            "controller_paths", Parameter.Type.STRING_ARRAY
        )
        self.declare_parameter("plugin_dirs", Parameter.Type.STRING_ARRAY)
        self.declare_parameter("strict_mode", False)
        self.declare_parameter("controller_shutdown_timeout", 10.0)

        controller_paths = list(self.get_parameter("controller_paths").value)
        plugin_dirs = list(self.get_parameter("plugin_dirs").get_parameter_value().string_array_value)
        self.strict_mode = bool(self.get_parameter("strict_mode").value)
        self.controller_shutdown_timeout = float(
            self.get_parameter("controller_shutdown_timeout").value
        )
        if self.controller_shutdown_timeout < 0:
            raise ValueError("controller_shutdown_timeout cannot be negative")

        self._controller_databus = Databus()
        controllers, load_issues = load_controllers(
            controller_paths, plugin_dirs, self._controller_databus
        )
        self._report_plugin_load_issues(load_issues)
        if self.strict_mode and load_issues:
            raise RuntimeError(
                f"Strict plugin loading failed for {len(load_issues)} item(s)"
            )
        if not controllers:
            raise RuntimeError("No hardware controllers could be loaded")
        self._ensure_unique_controller_names(controllers)
        try:
            self._controller_databus.finalize()
        except DatabusError as error:
            raise RuntimeError(f"Controller databus topology is invalid: {error}") from error

        self.loaded_hw_controllers = controllers
        self.dispatcher: Dispatcher[int, MotionCommand] = Dispatcher()
        for controller in self.loaded_hw_controllers:
            for command_id in controller.command_group:
                self.dispatcher.add_handler(
                    command_id, controller.enqueue_command
                )

        self._controller_events: SimpleQueue[
            tuple[str, LifecycleEvent]
        ] = SimpleQueue()
        self._last_controller_events: dict[str, LifecycleEvent] = {}
        self._controller_runners: list[LifecycleRunner] = []
        self._controller_threads: list[threading.Thread] = []
        self._runners_by_name: dict[str, LifecycleRunner] = {}
        self._controller_lock = threading.RLock()
        self._is_active = False

        self.updater = Updater(self)
        self.updater.setHardwareID("hardware_manager")
        for controller in self.loaded_hw_controllers:
            self.updater.add(
                f"controller-{controller.name}",
                lambda status, ctrl=controller: self._check_controller_status(
                    status, ctrl
                ),
            )
        self.create_timer(0.1, self._consume_controller_events)
        self.create_timer(1.0, self.updater.update)
        self.hb = HeartbeatGenerator(
            self, 5, 5, process_names.HARDWARE_MANAGER
        )

        self.create_subscription(
            MotionframeArray, INPUT_TOPIC, self.motionframe_callback, 5
        )
        self.create_subscription(
            String, CONFIG_TOPIC, self.update_config_callback, 5
        )
        self.get_logger().info(
            f"Loaded {len(self.loaded_hw_controllers)} hardware controller(s)"
        )

    def _report_plugin_load_issues(
        self, issues: list[PluginLoadIssue]
    ) -> None:
        for issue in issues:
            self.get_logger().warning(
                f"Skipping controller plugin '{issue.source}': {issue.message}"
            )

    def _ensure_unique_controller_names(
        self, controllers: list[BaseHardwareController]
    ) -> None:
        names = [controller.name for controller in controllers]
        if len(set(names)) != len(names):
            raise ValueError("Controller plugin names must be unique")

    def _make_runner(self, controller: BaseHardwareController) -> LifecycleRunner:
        controller_logger = self.get_logger().get_child(controller.name)
        event_sink = FanOutEventSink(
            [
                RcutilsEventSink(controller_logger, controller.name),
                ControllerEventSink(controller.name, self._controller_events),
            ]
        )
        return LifecycleRunner(
            controller,
            initial_target=ControllerState.INACTIVE,
            event_sink=event_sink,
        )

    def _start_controller_runners(self) -> bool:
        with self._controller_lock:
            if any(thread.is_alive() for thread in self._controller_threads):
                self.get_logger().error(
                    "Cannot configure while controller runner threads are alive"
                )
                return False
            if any(
                runner.get_live_state() != ControllerState.FINALIZED
                for runner in self._controller_runners
            ):
                self.get_logger().error(
                    "Cannot restart controllers before their previous runners finalize"
                )
                return False

            runners: list[LifecycleRunner] = []
            threads: list[threading.Thread] = []
            try:
                for controller in self.loaded_hw_controllers:
                    runner = self._make_runner(controller)
                    thread = threading.Thread(
                        target=runner.run,
                        name=f"lifecycle-{controller.name}",
                        daemon=True,
                    )
                    thread.start()
                    runners.append(runner)
                    threads.append(thread)
            except RuntimeError as error:
                self.get_logger().error(
                    f"Failed to start controller runners: {error}"
                )
                self._controller_runners = runners
                self._controller_threads = threads
                self._runners_by_name = {
                    controller.name: runner
                    for controller, runner in zip(
                        self.loaded_hw_controllers, runners
                    )
                }
                self._stop_controller_runners()
                return False

            self._controller_runners = runners
            self._controller_threads = threads
            self._runners_by_name = {
                controller.name: runner
                for controller, runner in zip(
                    self.loaded_hw_controllers, runners
                )
            }
            return True

    def _stop_controller_runners(self) -> bool:
        with self._controller_lock:
            for runner in self._controller_runners:
                try:
                    runner.set_target_state(ControllerState.FINALIZED)
                except ValueError as error:
                    self.get_logger().error(
                        f"Failed to finalize a controller runner: {error}"
                    )
                    return False

            deadline = time.monotonic() + self.controller_shutdown_timeout
            for thread in self._controller_threads:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))

            alive = [
                thread.name
                for thread in self._controller_threads
                if thread.is_alive()
            ]
            unfinished = [
                runner
                for runner in self._controller_runners
                if runner.get_live_state() != ControllerState.FINALIZED
            ]
            if alive or unfinished:
                detail = ", ".join(alive) or "controller did not finalize"
                self.get_logger().error(
                    f"Controller cleanup timed out or failed: {detail}"
                )
                return False

            for controller in self.loaded_hw_controllers:
                controller.clear_pending_work()
            self._controller_runners.clear()
            self._controller_threads.clear()
            self._runners_by_name.clear()
            return True

    def _set_controller_targets(self, target: ControllerState) -> bool:
        with self._controller_lock:
            try:
                for runner in self._controller_runners:
                    runner.set_target_state(target)
            except ValueError as error:
                self.get_logger().error(
                    f"Unable to set controller target to {target.name}: {error}"
                )
                return False
        return True

    def _consume_controller_events(self) -> None:
        while True:
            try:
                controller_name, event = self._controller_events.get_nowait()
            except Empty:
                return
            self._last_controller_events[controller_name] = event

    def _check_controller_status(
        self,
        status: DiagnosticStatusWrapper,
        controller: BaseHardwareController,
    ) -> DiagnosticStatusWrapper:
        with self._controller_lock:
            runner = self._runners_by_name.get(controller.name)

        if runner is None:
            live_state = ControllerState.UNCONFIGURED
            target_state = ControllerState.UNCONFIGURED
        else:
            live_state = runner.get_live_state()
            target_state = runner.get_target_state()

        if live_state == ControllerState.FAULTED:
            status.summary(
                DiagnosticStatus.ERROR,
                f"Controller {controller.name} is faulted",
            )
        elif live_state != target_state:
            status.summary(
                DiagnosticStatus.WARN,
                f"Controller {controller.name} is transitioning",
            )
        else:
            status.summary(
                DiagnosticStatus.OK,
                f"Controller {controller.name} is {live_state.name}",
            )

        status.add("live_state", live_state.name)
        status.add("target_state", target_state.name)
        event = self._last_controller_events.get(controller.name)
        if event is not None:
            status.add("last_event", event.message or type(event).__name__)
        return status

    def update_config_callback(self, message: String) -> None:
        if not self._is_active:
            return
        try:
            config = json.loads(message.data)
        except json.JSONDecodeError as error:
            self.get_logger().warning(f"Failed to parse config update: {error}")
            return
        if not isinstance(config, dict):
            self.get_logger().warning("Config update must be a JSON object")
            return
        for controller in self.loaded_hw_controllers:
            controller.enqueue_config_update(config)

    def motionframe_callback(self, message: MotionframeArray) -> None:
        if not self._is_active:
            return
        for command_id, value in zip(message.ids, message.values):
            command = MotionCommand(command_id, value)
            self.dispatcher.dispatch((command_id, command))

    def on_configure(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug("Configuring hardware controllers")
        if not self._start_controller_runners():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_activate(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug("Activating hardware controllers")
        if not self._set_controller_targets(ControllerState.ACTIVE):
            return TransitionCallbackReturn.FAILURE
        self._is_active = True
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug("Deactivating hardware controllers")
        self._is_active = False
        if not self._set_controller_targets(ControllerState.INACTIVE):
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug("Finalizing hardware controllers")
        self._is_active = False
        if not self._stop_controller_runners():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().debug("Shutting down hardware controllers")
        self._is_active = False
        if not self._stop_controller_runners():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def on_error(
        self, state: RosLifecycleState
    ) -> TransitionCallbackReturn:
        self.get_logger().error("Stopping hardware controllers after lifecycle error")
        self._is_active = False
        if not self._stop_controller_runners():
            return TransitionCallbackReturn.FAILURE
        return TransitionCallbackReturn.SUCCESS

    def destroy_node(self) -> bool:
        self._is_active = False
        if not self._stop_controller_runners():
            self.get_logger().error(
                "Some controller threads remain alive during node destruction"
            )
        return super().destroy_node()
