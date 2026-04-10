from dataclasses import dataclass
from enum import Enum, auto
from typing import List

from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController
from .looper import LoopDescriptor, LoopSupervisor


class ControllerState(Enum):
    """
    Desired state of a controller + loop pair.
    """
    UNINITIALIZED = auto()
    INITIALIZED = auto()
    RUNNING = auto()


@dataclass
class ManagedController:
    """
    Internal structure holding a controller, its loop and desired goal.
    """
    loop: LoopDescriptor
    controller: BaseHardwareController
    goal: ControllerState = ControllerState.UNINITIALIZED
    state: ControllerState = ControllerState.UNINITIALIZED


class HWControllerStateReconciler:
    """
    Reconciles the state of hardware controllers and their associated loops
    toward a desired goal state.

    The reconciler periodically checks the actual system state and attempts
    to move it toward the desired state. This replaces retry queues and
    transition-specific recovery logic.
    """

    def __init__(self, looper: LoopSupervisor, logger: RcutilsLogger):
        self.looper = looper
        self.logger = logger
        self.controllers: List[ManagedController] = []

    # ------------------------------------------------------------------
    # Controller registration
    # ------------------------------------------------------------------

    def add_controller(self, loop: LoopDescriptor, controller: BaseHardwareController):
        """
        Register a controller + loop pair to be managed by the reconciler.
        """
        self.controllers.append(
            ManagedController(loop=loop, controller=controller)
        )

    # ------------------------------------------------------------------
    # Goal management
    # ------------------------------------------------------------------

    def set_goal(self, loop_id: int, goal: ControllerState):
        """
        Set the desired goal for a specific controller.
        """
        for c in self.controllers:
            if c.loop.id == loop_id:
                c.goal = goal
                return

    def set_goal_all(self, goal: ControllerState):
        """
        Set the desired goal for all controllers.
        """
        for c in self.controllers:
            c.goal = goal

    # ------------------------------------------------------------------
    # Reconciliation loop
    # ------------------------------------------------------------------

    def reconcile(self):
        """
        Attempt to move each controller toward its desired state.
        Should be called periodically (e.g. by a ROS timer).
        """

        for mc in self.controllers:
            try:
                if mc.goal == ControllerState.RUNNING:
                    self._ensure_running(mc)

                elif mc.goal == ControllerState.INITIALIZED:
                    self._ensure_initialized(mc)

                elif mc.goal == ControllerState.UNINITIALIZED:
                    self._ensure_uninitialized(mc)

            except Exception as e:
                self.logger.warning(
                    f"Reconciliation error for controller '{mc.controller.name}': {e}"
                )

    # ------------------------------------------------------------------
    # Goal enforcement helpers
    # ------------------------------------------------------------------

    def _ensure_running(self, mc: ManagedController):
        """
        Ensure controller is initialized and loop is running.
        """
        if mc.state == ControllerState.RUNNING:
            return

        self._ensure_initialized(mc)
        if mc.state != ControllerState.INITIALIZED:
            return

        if not self.looper.resume_loop(mc.loop.id):
            self.logger.warning(f"Failed to resume loop '{mc.loop.name}'")
            return

        mc.state = ControllerState.RUNNING
        
    def _ensure_initialized(self, mc: ManagedController):
        """
        Ensure controller is initialized but loop is paused.
        """

        if mc.state == ControllerState.INITIALIZED:
            return

        # we can also come from running state
        if mc.state != ControllerState.RUNNING:
            self._ensure_uninitialized(mc)
            if mc.state != ControllerState.UNINITIALIZED:
                return

        if not mc.controller.initialize_hw():
            self.logger.warning(
                f"Failed to initialize controller '{mc.controller.name}'"
            )
            return

        if not self.looper.start_loop(mc.loop.id, paused=True):
            self.logger.warning(f"Failed to start loop '{mc.loop.name}'")
            return

        mc.state = ControllerState.INITIALIZED

    def _ensure_uninitialized(self, mc: ManagedController):
        """
        Ensure controller is fully stopped and deinitialized.
        """

        if mc.state == ControllerState.UNINITIALIZED:
            return

        if mc.loop.is_running:
            self.looper.stop_loop(mc.loop.id)
            if mc.loop.is_running:
                self.logger.warning(f"Failed to stop loop '{mc.loop.name}'")
                return

        if not mc.controller.deinitialize_hw():
            self.logger.warning(
                f"Failed to deinitialize controller '{mc.controller.name}'"
            )
            return

        mc.state = ControllerState.UNINITIALIZED