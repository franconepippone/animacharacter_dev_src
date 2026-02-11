"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
import importlib
import rclpy
from rclpy.logging import RcutilsLogger

from .abstract_config import AbstractConfiguration
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher
from .looper_util import ThreadedLooper


logger = RcutilsLogger('HW mng startup')

def main(args=None):
    # THIS IS PROBABLY VERY BROKEN!
    cfg_module = importlib.import_module('hardware_mng.configs.teodore_cfg')
    cfg: AbstractConfiguration = getattr(cfg_module, 'get_config_class')()() # create an instance
    logger.info(f"Import succeded {cfg} {type(cfg)}")
    
    dispatcher: Dispatcher[int, float] = Dispatcher()
    cfg.configure_dispatcher(dispatcher)
    
    looper = ThreadedLooper()
    for driver in cfg.get_drivers():
        looper.add_loop(driver.loop_freq, driver.driver.drive_hardware)

    #looper.pause_loop(l1.id)
    #looper.resume_loop(l2.id)
    
    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(dispatcher, looper)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
