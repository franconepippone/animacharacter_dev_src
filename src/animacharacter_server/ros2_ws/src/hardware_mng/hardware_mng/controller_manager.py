from __future__ import annotations

from collections.abc import Callable, Iterable
import threading
import time
from typing import cast

from diagnostic_updater import DiagnosticStatusWrapper
from lifecycle_pkg import LifecycleThreadedRunner
from lifecycle_pkg.events import FanOutEventSink, LifecycleEvent
from lifecycle_pkg.events import State as ControllerState
from rclpy.lifecycle import LifecycleNode
from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController, MotionCommand
from .controller_diagnostics import make_controller_status
from .databus import Databus, DatabusError
from .dispatcher import Dispatcher
from .event_sinks import (
    ControllerEventSink,
    ExecutorEventQueue,
    RcutilsEventSink,
)
from .plugins_loader import load_controllers, PluginLoadIssue


class ControllerManager:
    """Own hardware plugins, their runners, and controller-facing operations."""

    def __init__(
        self,
        node: LifecycleNode,
        controller_paths: list[str],
        plugin_dirs: list[str],
        strict_mode: bool,
        operation_timeout: float,
    ) -> None:
        self._node = node
        self._logger: RcutilsLogger = node.get_logger()
        self._operation_timeout = operation_timeout
        if operation_timeout < 0:
            raise ValueError('controller_operation_timeout cannot be negative')

        self._controller_databus = Databus()
        controllers, load_issues = load_controllers(
            controller_paths, plugin_dirs, self._controller_databus
        )
        self._report_plugin_load_issues(load_issues)
        if strict_mode and load_issues:
            raise RuntimeError(
                f'Strict plugin loading failed for {len(load_issues)} item(s)'
            )
        if not controllers:
            raise RuntimeError('No hardware controllers could be loaded')
        self._ensure_unique_controller_names(controllers)
        try:
            self._controller_databus.finalize()
        except DatabusError as error:
            raise RuntimeError(
                f'Controller databus topology is invalid: {error}'
            ) from error

        self.controllers = controllers
        self.dispatcher: Dispatcher[int, MotionCommand] = Dispatcher()
        for controller in self.controllers:
            for command_id in controller.command_group:
                self.dispatcher.add_handler(
                    command_id, controller.enqueue_command
                )

        self._controller_events: ExecutorEventQueue[
            tuple[str, LifecycleEvent]
        ] = ExecutorEventQueue()
        self._last_controller_events: dict[str, LifecycleEvent] = {}
        self._event_consumer_started = False
        self._controller_runners: list[LifecycleThreadedRunner] = []
        self._runners_by_name: dict[str, LifecycleThreadedRunner] = {}
        self._controller_lock = threading.RLock()
        self._is_active = False

    def _report_plugin_load_issues(
        self, issues: list[PluginLoadIssue]
    ) -> None:
        for issue in issues:
            self._logger.warning(
                f"Skipping controller plugin '{issue.source}': {issue.message}"
            )

    @staticmethod
    def _ensure_unique_controller_names(
        controllers: list[BaseHardwareController],
    ) -> None:
        names = [controller.name for controller in controllers]
        if len(set(names)) != len(names):
            raise ValueError('Controller plugin names must be unique')

    def _make_runner(
        self, controller: BaseHardwareController
    ) -> LifecycleThreadedRunner:
        event_sink = FanOutEventSink(
            [
                RcutilsEventSink(controller.logger, controller.name),
                ControllerEventSink(controller.name, self._controller_events),
            ]
        )
        return LifecycleThreadedRunner(
            controller,
            initial_target=ControllerState.INACTIVE,
            event_sink=event_sink,
            thread_name=f'lifecycle-{controller.name}',
        )

    def _start_controller_runners(self) -> bool:
        with self._controller_lock:
            if any(runner.is_alive() for runner in self._controller_runners):
                self._logger.error(
                    'Cannot configure while controller runner threads are alive'
                )
                return False
            if any(
                runner.get_live_state() != ControllerState.FINALIZED
                for runner in self._controller_runners
            ):
                self._logger.error(
                    'Cannot restart controllers before their previous runners finalize'
                )
                return False

            runners: list[LifecycleThreadedRunner] = []
            try:
                for controller in self.controllers:
                    runner = self._make_runner(controller)
                    runner.start()
                    runners.append(runner)
            except RuntimeError as error:
                self._logger.error(
                    f'Failed to start controller runners: {error}'
                )
                self._controller_runners = runners
                self._runners_by_name = {
                    controller.name: runner
                    for controller, runner in zip(self.controllers, runners)
                }
                self._stop_controller_runners()
                return False

            self._controller_runners = runners
            self._runners_by_name = {
                controller.name: runner
                for controller, runner in zip(self.controllers, runners)
            }
            return True

    def _set_controller_targets(self, target: ControllerState) -> bool:
        with self._controller_lock:
            try:
                for runner in self._controller_runners:
                    runner.set_target_state(target)
            except ValueError as error:
                self._logger.error(
                    f'Unable to set controller target to {target.name}: {error}'
                )
                return False
        return True

    def _wait_for_reconciliation(
        self,
        target: ControllerState,
        deadline: float,
    ) -> bool:
        while True:
            with self._controller_lock:
                reconciled = all(
                    runner.get_live_state() == target
                    for runner in self._controller_runners
                )
            if reconciled:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))

    def _controller_situation(self) -> str:
        with self._controller_lock:
            return '; '.join(
                f'{name}(live={runner.get_live_state().name}, '
                f'target={runner.get_target_state().name})'
                for name, runner in self._runners_by_name.items()
            )

    def _wait_for_target(self, target: ControllerState) -> bool:
        reconciled = self._wait_for_reconciliation(
            target, time.monotonic() + self._operation_timeout
        )
        if not reconciled:
            self._logger.warning(
                f'Controller state reconciliation to {target.name} timed out '
                f'after {self._operation_timeout:.1f}s: '
                f"{self._controller_situation() or 'no controller runners'}"
            )
        return reconciled

    def _stop_controller_runners(self) -> bool:
        with self._controller_lock:
            if not self._set_controller_targets(ControllerState.FINALIZED):
                return False

            deadline = time.monotonic() + self._operation_timeout
            self._wait_for_reconciliation(
                ControllerState.FINALIZED, deadline
            )
            for runner in self._controller_runners:
                runner.join(timeout=max(0.0, deadline - time.monotonic()))

            alive = [
                runner.thread_name
                for runner in self._controller_runners
                if runner.is_alive()
            ]
            unfinished = [
                runner
                for runner in self._controller_runners
                if runner.get_live_state() != ControllerState.FINALIZED
            ]
            if alive or unfinished:
                self._logger.warning(
                    'Controller finalization did not reconcile within '
                    f'{self._operation_timeout:.1f}s: '
                    f"{self._controller_situation() or 'no controller runners'}"
                    + (f"; still-running threads: {', '.join(alive)}" if alive else '')
                )
                return True

            for controller in self.controllers:
                controller.clear_pending_work()
            self._controller_runners.clear()
            self._runners_by_name.clear()
            return True

    async def _consume_controller_events(self) -> None:
        while True:
            controller_name, event = await self._controller_events.get()
            with self._controller_lock:
                self._last_controller_events[controller_name] = event

    def _start_event_consumer(self) -> None:
        if self._event_consumer_started:
            return
        executor = self._node.executor
        if executor is None:
            raise RuntimeError(
                'Hardware manager must be attached to a ROS executor before configure'
            )
        self._controller_events.attach_executor(executor)
        executor.create_task(
            cast(Callable[[], None], self._consume_controller_events())
        )
        self._event_consumer_started = True

    def check_controller_status(
        self,
        status: DiagnosticStatusWrapper,
        controller: BaseHardwareController,
    ) -> DiagnosticStatusWrapper:
        with self._controller_lock:
            runner = self._runners_by_name.get(controller.name)
            event = self._last_controller_events.get(controller.name)
        if runner is None:
            live_state = ControllerState.UNCONFIGURED
            target_state = ControllerState.UNCONFIGURED
        else:
            live_state = runner.get_live_state()
            target_state = runner.get_target_state()

        return make_controller_status(
            status,
            controller.name,
            live_state,
            target_state,
            event,
        )

    def enqueue_config_update(self, config: dict[str, object]) -> None:
        if not self._is_active:
            return
        for controller in self.controllers:
            controller.enqueue_config_update(config)

    def dispatch_motionframes(
        self, command_ids: Iterable[int], values: Iterable[float]
    ) -> None:
        if not self._is_active:
            return
        for command_id, value in zip(command_ids, values):
            command = MotionCommand(command_id, value)
            self.dispatcher.dispatch((command_id, command))

    def awake(self) -> bool:
        self._start_event_consumer()
        if not self._start_controller_runners():
            return False
        self._wait_for_target(ControllerState.INACTIVE)
        return True

    def activate(self) -> bool:
        if not self._set_controller_targets(ControllerState.ACTIVE):
            return False
        self._is_active = True
        self._wait_for_target(ControllerState.ACTIVE)
        return True

    def deactivate(self) -> bool:
        self._is_active = False
        if not self._set_controller_targets(ControllerState.INACTIVE):
            return False
        self._wait_for_target(ControllerState.INACTIVE)
        return True

    def shutdown(self) -> bool:
        self._is_active = False
        return self._stop_controller_runners()

    def handle_error(self) -> bool:
        self._is_active = False
        return self._stop_controller_runners()
