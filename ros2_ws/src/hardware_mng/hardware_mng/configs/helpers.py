from mcudrivers import HeadMcuDriver
from mcudrivers.head_driver import Axis

# consider shipping such classes in the mcudriver itself? 
class eyesDriverHelper:
    def __init__(self, driver: HeadMcuDriver) -> None:
        self.d = driver
        self.focus: float = 0
        self.eyes_h: float = 0

    def set_eyes_h(self, val: float):
        self.eyes_h = val
        self.write()
    
    def set_focus(self, val: float):
        self.focus = val
        self.write()

    def write(self):
        # TODO compute actual angles
        self.d.write(Axis.EYE_L, self.eyes_h)
        self.d.write(Axis.EYE_R, self.eyes_h)