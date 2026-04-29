from functools import cache
from typing import Tuple
from enum import Enum


class BehaviorActionType(Enum):
    STOP = 0
    CONTINUE = 1
    SLEEP = 2

type BehaviorActionRaw = Tuple[BehaviorActionType, float] # generic (type, arg) format

class BehaviorAction:
    """
    Implements functions to be called when yielding on a behavior to
    request a specific action (continue is the default)
    """
    @staticmethod
    def sleep(seconds: float):
        """Put the bahavior to sleep for a certain amount of seconds."""
        return BehaviorActionType.SLEEP, seconds
    
    @staticmethod
    @cache
    def loop(freq: float):
        """Put the behavior to sleep for the amount of seconds corresponding to the given frequency in Hz."""
        return BehaviorActionType.SLEEP, 1.0/freq

    @staticmethod
    def stop(): 
        """Stop the behavior and remove it from the executor."""
        return BehaviorActionType.STOP, 0
    
    @staticmethod
    def continue_():
        """Continue the behavior without sleeping or stopping (default action when yielding None)."""
        return BehaviorActionType.CONTINUE, 0