from dataclasses import dataclass
from enum import Enum, auto
from typing import List

from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController
from .looper import LoopDescriptor, LoopSupervisor


class ControllerState(Enum):
    """
    Logical controller state.
    """
    UNINITIALIZED = auto()
    INITIALIZED = auto()
    RUNNING = auto()


@dataclass
class ManagedController:
    """
    Holds the controller and loop plus the desired goal.
    """
    loop: LoopDescriptor
    controller: BaseHardwareController
    goal: ControllerState = ControllerState.UNINITIALIZED


class HWControllerStateReconciler:
    """
    Desired-state reconciler for hardware controllers and loops.
    """

    def __init__(self, looper: LoopSupervisor, logger: RcutilsLogger):
        self.looper = looper
        self.logger = logger
        self.controllers: List[ManagedController] = []

    # Controller registration

    def add_controller(self, loop: LoopDescriptor, controller: BaseHardwareController):
        self.controllers.append(
            ManagedController(loop=loop, controller=controller)
        )

    # Goal management

    def set_goal(self, loop_id: int, goal: ControllerState):
        for mc in self.controllers:
            if mc.loop.id == loop_id:
                mc.goal = goal
                return

    def set_goal_all(self, goal: ControllerState):
        for mc in self.controllers:
            mc.goal = goal

    # State observation

    def _actual_state(self, mc: ManagedController) -> ControllerState:
        """
        Derive the controller state from the real system.
        
        Logic:
        - RUNNING: Loop is started AND not paused AND HW is init.
        - INITIALIZED: Loop is started AND paused AND HW is init.
        - UNINITIALIZED: Anything else (Loop stopped or HW not init).
        """
        hw_init = mc.controller.is_initialized()
        loop_running = mc.loop.is_running
        loop_paused = self.looper.is_paused(mc.loop.id)

        if hw_init and loop_running and not loop_paused:
            return ControllerState.RUNNING
        
        if hw_init and loop_running and loop_paused:
            return ControllerState.INITIALIZED

        return ControllerState.UNINITIALIZED

    # Reconciliation loop

    def reconcile(self):
        """
        Attempt to move the system toward desired state.
        """
        for mc in self.controllers:
            try:
                actual = self._actual_state(mc)
                goal = mc.goal

                if actual == goal:
                    continue

                self.logger.info(
                    f"Reconciling '{mc.controller.name}': {actual.name} -> {goal.name}"
                )

                if goal == ControllerState.RUNNING:
                    self._step_to_running(mc, actual)
                elif goal == ControllerState.INITIALIZED:
                    self._step_to_initialized(mc, actual)
                elif goal == ControllerState.UNINITIALIZED:
                    self._step_to_uninitialized(mc, actual)

            except Exception as e:
                self.logger.error(
                    f"Reconciliation error for '{mc.controller.name}': {e}"
                )

    # Transition steps (State Machine Logic)

    def _step_to_running(self, mc: ManagedController, actual: ControllerState):
        """Move toward RUNNING."""
        if actual == ControllerState.UNINITIALIZED:
            # First, get to INITIALIZED
            self._step_to_initialized(mc, actual)
        
        elif actual == ControllerState.INITIALIZED:
            # Resume to reach RUNNING
            if not self.looper.resume_loop(mc.loop.id):
                self.logger.warning(f"Failed to resume loop '{mc.loop.name}'")

    def _step_to_initialized(self, mc: ManagedController, actual: ControllerState):
        """Move toward INITIALIZED (HW Init + Loop Paused)."""
        if actual == ControllerState.UNINITIALIZED:
            # 1. Initialize Hardware
            if not mc.controller.is_initialized():
                if not mc.controller.initialize_hw():
                    self.logger.warning(f"HW init failed for '{mc.controller.name}'")
                    return

            # 2. Start the loop in paused mode
            if not mc.loop.is_running:
                if not self.looper.start_loop(mc.loop.id, paused=True):
                    self.logger.warning(f"Failed to start loop '{mc.loop.name}'")
            else:
                # If loop was running but HW wasn't init (error state), pause it
                self.looper.pause_loop(mc.loop.id)

        elif actual == ControllerState.RUNNING:
            # Just pause it
            if not self.looper.pause_loop(mc.loop.id):
                self.logger.warning(f"Failed to pause loop '{mc.loop.name}'")

    def _step_to_uninitialized(self, mc: ManagedController, actual: ControllerState):
        """Move toward UNINITIALIZED (Loop Stopped + HW Deinit)."""
        # 1. Stop the loop first (Safety)
        if mc.loop.is_running:
            if not self.looper.stop_loop(mc.loop.id):
                self.logger.warning(f"Failed to stop loop '{mc.loop.name}'")
                return

        # 2. Deinitialize Hardware
        if mc.controller.is_initialized():
            if not mc.controller.deinitialize_hw():
                self.logger.warning(f"HW deinit failed for '{mc.controller.name}'")

    def get_status_for_controller_json(self, mc: ManagedController):
        actual = self._actual_state(mc)
        return {
                "goal": mc.goal.name,
                "state": actual.name,
                "loop_running": mc.loop.is_running,
                "hw_initialized": mc.controller.is_initialized()
            }

    # Status 
    def get_status_json(self):
        status = {}
        has_discrepancy = False # wheter there is at least one controller in an unwanted state
        for mc in self.controllers:
            actual = self._actual_state(mc)
            status[mc.controller.name] = self.get_status_for_controller_json(mc)
            if mc.goal.name != actual.name:
                has_discrepancy = True
        status["has_discrepancy"] = has_discrepancy
        return status

    def get_ascii_status(self) -> str:
        """
        Returns a formatted ASCII table representing the current 
        reconciliation status of all managed controllers.
        
        Rows with an ACTUAL-GOAL mismatch are highlighted in Yellow.
        """
        if not self.controllers:
            return "No controllers registered."

        # ANSI Escape Codes
        RED = "\033[91m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        # Define column widths
        name_w = 25
        state_w = 15
        bool_w = 10

        # Header
        header = (
            f"{'CONTROLLER':<{name_w}} | "
            f"{'ACTUAL':<{state_w}} | "
            f"{'GOAL':<{state_w}} | "
            f"{'LOOP':<{bool_w}} | "
            f"{'HW':<{bool_w}}"
        )
        separator = "-" * len(header)

        lines = [separator, f"{BOLD}{header}{RESET}", separator]

        for mc in self.controllers:
            actual = self._actual_state(mc)
            
            # Formatting values
            name = (mc.controller.name[:name_w-3] + '...') if len(mc.controller.name) > name_w else mc.controller.name
            actual_str = actual.name
            goal_str = mc.goal.name
            
            # Using your updated status logic
            loop_status = ("PAUSED" if self.looper.is_paused(mc.loop.id) else "RUNNING") if mc.loop.is_running else "STOP"
            hw_status = "OK" if mc.controller.is_initialized() else "DOWN"

            row = (
                f"{name:<{name_w}} | "
                f"{RED if actual != mc.goal else ""}{actual_str:<{state_w}} | {RESET}"
                f"{RED if actual != mc.goal else ""}{goal_str:<{state_w}} | {RESET}"
                f"{loop_status:<{bool_w}} | "
                f"{hw_status:<{bool_w}}"
            )

            # Color row if actual state doesn't match the goal
            if actual != mc.goal:
                lines.append(f"{RED}{row}{RESET}")
            else:
                lines.append(row)

        lines.append(separator)
        return "\n".join(lines)