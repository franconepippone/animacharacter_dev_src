"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
import importlib
import rclpy
from rclpy.logging import RcutilsLogger

from .abstract_config import AbstractHMSConfiguration
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher
from .looper_util import ThreadedLooper


logger = RcutilsLogger('HW-mng startup')

def import_config(path: str) -> AbstractHMSConfiguration | None:
    """ Attempts import of configuration module at runtime """
    try:
        cfg_module = importlib.import_module(path)
        cfg: AbstractHMSConfiguration = getattr(cfg_module, 'get_config')() # gets the config instance

        if not isinstance(cfg, AbstractHMSConfiguration):
            raise ValueError(f"Configuration object is of type '{type(cfg)}' instead of subtype of AbstractHMSConfiguration")
        return cfg
    except Exception as e:
        logger.error(f"Failed to import configuration hardware system configuration '{path}': {e}")


def main(args=None):
    # this eventually will be provided by env vars or CLI arguments
    CONFIG_MODULE_PATH = 'hardware_mng.configs.teodore_cfg'
    cfg = import_config(CONFIG_MODULE_PATH)
    if not cfg:
        return 
     
    logger.info(f"Import succeded {cfg} {type(cfg)}")
    
    dispatcher: Dispatcher[int, float] = Dispatcher()
    cfg.configure_dispatcher(dispatcher)
    
    looper = ThreadedLooper()
    for driver in cfg.get_drivers():
        looper.add_loop(driver.loop_freq, driver.driver.flush)

    #looper.pause_loop(l1.id)
    #looper.resume_loop(l2.id)
    
    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(dispatcher, looper)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
