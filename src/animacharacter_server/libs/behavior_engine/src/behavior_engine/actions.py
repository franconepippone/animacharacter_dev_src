from functools import cache
from typing import Tuple
from enum import Enum


class BehaviorActionType(Enum):
    STOP = 0
    CONTINUE = 1
    SLEEP = 2
    TICK = 3

type BehaviorActionRaw = Tuple[BehaviorActionType, float] # generic (type, arg) format

class BehaviorAction:
    """
    Implements functions to be called when yielding on a behavior to
    request a specific action (continue is the default)
    """
    @staticmethod
    def sleep(seconds: float):
        """Put the behavior to sleep for a certain amount of seconds."""
        return BehaviorActionType.SLEEP, seconds
    
    @staticmethod
    def tick(freq: float):
        """Attempts to awake the behaviour in time to ensure a constant frequency in Hz."""
        return BehaviorActionType.TICK, freq

    @staticmethod
    def stop(): 
        """Stop the behavior and remove it from the executor."""
        return BehaviorActionType.STOP, 0
    
    @staticmethod
    def continue_():
        """Continue the behavior without sleeping or stopping (default action when yielding None).
        This resumes the behaviour as soon as possible.
        """
        return BehaviorActionType.CONTINUE, 0