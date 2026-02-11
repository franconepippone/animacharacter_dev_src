from animacharacter_server.ros2_ws.src.hardware_mng.hardware_mng.dispatcher import Dispatcher
from hardware_mng.abstract_config import AbstractConfiguration

from mcudrivers import HeadMcuDriver
from mcudrivers.head_driver import Axys
from configdata.teodore.get_table import get_id_by_name_tb

PORT = 'COM3' # this should change based on OS or based on a ROS2 service
LOOP_FREQ = 50 #Hz

TABLE = get_id_by_name_tb()

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
        # compute actual angles
        self.d.write(Axys.EYE_L, self.eyes_h)
        self.d.write(Axys.EYE_R, self.eyes_h)

class TeodoreCfg(AbstractConfiguration):
    def __init__(self) -> None:
        super().__init__()
        self.head = self.add_driver('head_driver', HeadMcuDriver(PORT), LOOP_FREQ)

        self.eyes_helper = eyesDriverHelper(self.head)

    def configure_dispatcher(self, dispatcher: Dispatcher[int, bytes]):
        dispatcher.register_handler(TABLE['EYES_H'], self.eyes_helper.set_eyes_h)
        dispatcher.register_handler(TABLE['EYES_V'], lambda val: self.head.write(Axys.EYES_PITCH, val))
        ...