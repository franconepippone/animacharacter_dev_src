from random import random

from lifecycle_pkg import FaultContext, RecoveryResult, TransitionResult

from hardware_mng.abstract_hw_controller import BaseHardwareController, MotionCommand

# Simulate lifecycle failures.
def faultytrue(fault_chance: float, msg: str) -> bool:
    ok = random() > fault_chance
    print(msg, ok)
    return ok

class A_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("A", flush_freq=1)
        self.subscribe_to_command_group([1,2,3])
        self.faulty_cnt = 0

    def on_awake(self) -> TransitionResult:
        self.faulty_cnt += 1
        return (
            TransitionResult.SUCCESS
            if self.faulty_cnt > 5 and faultytrue(0.5, "Initializing A:")
            else TransitionResult.FAIL_RETRY
        )
    
    def on_activate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_deactivate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult:
        return TransitionResult.SUCCESS if faultytrue(0.5, "Shutting down A:") else TransitionResult.FAIL_RETRY
    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        return RecoveryResult.success(fault.state_from)

    def control(self, commands: list[MotionCommand]): print(f"controlling A, got {len(commands)} commands")


class B_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("B", flush_freq=1.0)
        self.subscribe_to_command_group([4,5,6])
    
    def on_awake(self) -> TransitionResult:
        return TransitionResult.SUCCESS if faultytrue(0.6, "Initializing B:") else TransitionResult.FAIL_RETRY
    def on_activate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_deactivate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult:
        return TransitionResult.SUCCESS if faultytrue(0.7, "Shutting down B:") else TransitionResult.FAIL_RETRY
    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        return RecoveryResult.success(fault.state_from)

    def control(self, commands: list[MotionCommand]): print(f"controlling B, got {len(commands)} commands")


class C_Controller(BaseHardwareController):
    def __init__(self):
        super().__init__("C", flush_freq=1.0)
        self.subscribe_to_command_group([7,8,9])

    def on_awake(self) -> TransitionResult:
        return TransitionResult.SUCCESS if faultytrue(0.5, "Initializing C:") else TransitionResult.FAIL_RETRY
    def on_activate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_deactivate(self) -> TransitionResult: return TransitionResult.SUCCESS
    def on_shutdown(self) -> TransitionResult:
        return TransitionResult.SUCCESS if faultytrue(0.2, "Shutting down C:") else TransitionResult.FAIL_RETRY
    def on_recover(self, fault: FaultContext) -> RecoveryResult:
        return RecoveryResult.success(fault.state_from)

    def control(self, commands: list[MotionCommand]): print(f"controlling C, got {len(commands)} commands")
    def read(self):
        if not faultytrue(0.2, "testing read C:"):
            raise RuntimeError("C controller became unresponsive")