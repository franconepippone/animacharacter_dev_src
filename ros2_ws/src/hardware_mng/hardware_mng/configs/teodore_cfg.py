from hardware_mng.dispatcher import Dispatcher, BatchDispatcher, hooks_to_context
from hardware_mng.abstract_config import AbstractHMSConfiguration
from .helpers import eyesDriverHelper

from mcudrivers import HeadMcuDriver
from mcudrivers.mock_driver import MockDriver
from mcudrivers.head_driver import Axis
from configdata.teodore.table import teodore_actuator_table as TABLE, BODY_GROUP, HEAD_GROUP, LEFT_ARM_GROUP, RIGHT_ARM_GROUP

from rclpy.logging import RcutilsLogger

PORT = 'COM3' # this should change based on OS or based on a ROS2 service
LOOP_FREQ = 50 #Hz

class TeodoreHMSCfg(AbstractHMSConfiguration):
    """
    Implementation of a hardware manager system configuration for the 'Teodore' animacharacter;
    Teodore refers to the common, versitile strcuture used for the homonymous robot.
    The hardware is split into four microcontrollers, respectivelly controlled by 4 drivers:
    - **Head** : controls facial movements (eyes, mouth, ears) as well as neck movements (up/down, tilt, NOT horizontal rotation).
    - **Body** : controls torso movements, as well as head rotation (horizontal).
    - **Left Arm** : controls all movements of left arm and hand.
    - **Right Arm** : controls all movements of right arm and hand.
    
    The driver classes are found in the libs/mcuDrivers directory, beside /ros2_ws. The driver classes are completely independent of ros2,
    and can be used in other contexts as well. They just provide hardware control abstraction. 
    
    This configuration is the standard and is ment to be very general and well
    suited for controlling all kinds of similary shaped animatronics or robotic systems.
    """

    def __init__(self) -> None:
        super().__init__()
        self.head_logger = RcutilsLogger('Head Driver')
        self.body_logger = RcutilsLogger('Body Driver')
        self.head = self.add_driver('head_driver', HeadMcuDriver(PORT, logger=self.head_logger), LOOP_FREQ)
        self.body = self.add_driver('body_driver', MockDriver(logger=self.body_logger), 50)
        #self.body = self.add_driver('body', BodyMcuDriver(...), LOOP_FREQ)
        #self.left_arm = self.add_driver('left_arm', LeftArmDriver(...), LOOP_FREQ)
        #self.right_arm = self.add_driver('right_arm', RightArmDriver(...), LOOP_FREQ)

        self.eyes_helper = eyesDriverHelper(self.head)

    def configure_dispatcher(self, dispatcher: Dispatcher[int, float]):
        # here go all the mappings for individual id -> hardware axis pair (granular)
        dispatcher.register_handler(TABLE.EYES_H.id, self.eyes_helper.set_eyes_h)
        dispatcher.register_handler(TABLE.EYES_H.id, lambda val: self.head.write(Axis.EYES_PITCH, val))
        ...

        dispatcher.register_handler(50, lambda v: self.body.write_axis('axys_50_', v))
        dispatcher.register_handler(51, lambda v: self.body.write_axis('axys_51_', v))
        dispatcher.register_handler(52, lambda v: self.body.write_axis('axys_52_', v))
        dispatcher.register_handler(53, lambda v: self.body.write_axis('axys_53_', v))
        dispatcher.register_handler(100, lambda v: self.body.write_axis('axys_100_', v))
        dispatcher.register_handler(101, lambda v: self.body.write_axis('axys_101_', v))
        dispatcher.register_handler(105, lambda v: self.body.write_axis('axys_105_', v))

    def configure_batch_dispatcher(self, batch_dispatcher: BatchDispatcher[int, float]):
        

        batch_dispatcher.add_batch(
            {50,51,52, 53},
            hooks_to_context(lambda: self.body.logger.warning("entering dispatch A"), lambda: self.body.logger.warning("exiting dispatch A"))
        )
        batch_dispatcher.add_batch(
            {100, 101},
            hooks_to_context(lambda: self.body.logger.warning("entering dispatch B"), lambda: self.body.logger.warning("exiting dispatch B"))
        )

        # TODO when all drivers are implemented, add their respective locks here

        batch_dispatcher.add_batch(
            set(TABLE.get_ids_belonging_to_group(HEAD_GROUP)), 
            self.head.batch_write_lock()
        )
        batch_dispatcher.add_batch(
            set(TABLE.get_ids_belonging_to_group(BODY_GROUP)), 
            #self.head.batch_write_lock()
        )
        batch_dispatcher.add_batch(
            set(TABLE.get_ids_belonging_to_group(LEFT_ARM_GROUP)), 
            #self.head.batch_write_lock()
        )
        batch_dispatcher.add_batch(
            set(TABLE.get_ids_belonging_to_group(LEFT_ARM_GROUP)), 
            #self.head.batch_write_lock()
        )





# MAIN METHOD (IMPORTANT!)
def get_config() -> TeodoreHMSCfg:
    return TeodoreHMSCfg()