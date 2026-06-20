"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
from typing import Type
import rclpy
from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController, MotionCommand
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher
from .looper import LoopSupervisor, LoopDescriptor
from .databus import Databus, DatabusError
from . import plugins_loader as pld

import inspect

def is_type_of_base(obj, BaseClass):
    return inspect.isclass(obj) and issubclass(obj, BaseClass)

class ConcreteController(BaseHardwareController):
    def __init__(self) -> None: ...

logger = RcutilsLogger('HW-mng starter')

def main(args=None):
    # input is given via env variables
    import os
    PLUGIN_DIRS = os.getenv("PLUGIN_DIRS", "/plugins").split(":")
    CONFIG_FILE = os.getenv("CONFIG_FILE", "/config.yaml")
    INPUT_CONFIG = os.getenv("INPUT_CONFIG", "")
    STRICT_MODE = os.getenv("STRICT_MODE", "true").lower() == "true" #wheter to stop if any of the controllers fail to load

    pld.register_plugin_dirs(PLUGIN_DIRS) # now we can import them

    logger.debug(f"Plugins source directories are: {"\n\t- ".join(PLUGIN_DIRS)}")
    logger.debug(f"Configuration file source: {CONFIG_FILE}, current input config: {INPUT_CONFIG}")

    logger.info(f"Beginning hardare manager system initialization. CWD: {os.getcwd()}")

    # loading configs
    try:
        config_data: dict[str, list[str] | str] = pld.load_yaml_file(CONFIG_FILE)
    except RuntimeError as e:
        logger.fatal(f"Failed to load Hardware Configuration file -> {e}")
        exit(-1)

    if INPUT_CONFIG == '':
        default_config = config_data.get('default_config')
        if default_config is None or not isinstance(default_config, str):
            logger.fatal('No hardware configuration specified.')
            exit(-1)
        INPUT_CONFIG = default_config
    
    logger.info(f"Using configuration: '{INPUT_CONFIG}'")

    hw_controllers_paths: list[str] | str | None = config_data.get(INPUT_CONFIG)
    if hw_controllers_paths is None:
        logger.fatal(f"Configuration '{INPUT_CONFIG}' not found in hardware configuration file at '{CONFIG_FILE}'")
        exit(-1)
    if not(
        isinstance(hw_controllers_paths, list) and 
        all(isinstance(path, str) for path in hw_controllers_paths)
    ):
        logger.fatal(f"Invalid configuration '{INPUT_CONFIG}' (is not a list of paths (strings))")
        exit(-1)

    total = len(hw_controllers_paths)

    controllers: list[BaseHardwareController] = []
    
    # creating the shared databus for controllers
    databus = Databus()
    BaseHardwareController._databus = databus # binding at abstract class level

    # building controllers
    for i, path in enumerate(hw_controllers_paths):
        try:
            class_obj: Type[ConcreteController] = pld.import_class(path)
        except RuntimeError as e:
            logger.warning(f"[{i+1}/{total}] Failed to load hw controller at '{path}' -> {e}")
            continue
        
        if not is_type_of_base(class_obj, BaseHardwareController):
            logger.warning(f"[{i+1}/{total}] Controller at '{path}' class is not derived from 'BaseHardwareController'")
            continue

        try:
            controller = class_obj()
        except Exception as e:
            logger.warning(f"[{i+1}/{total}] Failed to instantiate hw controller at '{path}' -> {e}")
            continue
        
        if not isinstance(controller, BaseHardwareController):
            logger.warning(f"[{i+1}/{total}] Controller is of invalid class: {type(controller)}")
            continue


        logger.info(f"[{i+1}/{total}] loaded and instantiated hw controller at '{path}'")
        controllers.append(controller)
    
    # attempts to freeze databus topology
    try:
        databus.finalize()
    except DatabusError as e:
        logger.error(f"Databus finalization error -> {e}")
        logger.fatal(f"shutting down.")
        exit(-1)
    finally:
        logger.info(f"Databus finalized.")
    
    ok = len(controllers)
    if ok == total:
        logger.info(f"Succesfully loaded {ok}/{ok} hw controllers from configuration '{INPUT_CONFIG}'")
    elif not STRICT_MODE:
        logger.warning(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded. Hardware may not work completely.")
    else:
        logger.fatal(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded, shutting down.")
        exit(-1)

    # configure the dispatcher and looper
    looper = LoopSupervisor()
    dispatcher: Dispatcher[int, MotionCommand] = Dispatcher()
    
    loop_ctrl_pairs: list[tuple[LoopDescriptor, BaseHardwareController]] = []

    for ctrl in controllers:
        loop = looper.add_loop(f"loop-{ctrl.name}", ctrl.flush_freq, ctrl._flush, start_now=False)
        input_queue = loop.input_queue

        # we need q = input_queue because of how closures work 
        def handler(cmd: MotionCommand, q = input_queue) -> None:
            q.put(cmd, block=False)
        
        # make it so every received command gets put in the correct input queue.
        for id in ctrl.command_group:
            dispatcher.add_handler(id, handler)
        
        # keep the loop and respective controller boundled together in this tuple
        loop_ctrl_pairs.append((loop, ctrl))

    num_handlers = dispatcher.get_map_size()
    logger.info(f"Configuration complete, registered {num_handlers} dispatcher handlers. Starting ros node.")
    
    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(dispatcher, looper, loop_ctrl_pairs, databus)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
