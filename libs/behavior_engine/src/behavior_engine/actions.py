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
       return BehaviorActionType.SLEEP, seconds
    
    @staticmethod
    def stop(): 
        return BehaviorActionType.STOP, 0
    
    @staticmethod
    def continue_():
       return BehaviorActionType.CONTINUE, 0