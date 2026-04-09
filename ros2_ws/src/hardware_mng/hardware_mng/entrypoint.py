"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
import importlib
from types import ModuleType
import rclpy
from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher, BatchDispatcher
from .looper import LoopSupervisor

import yaml

from typing import Protocol

# used to avoid type checker for complaining down below...
class ControllerClass(Protocol):
    def __call__(self) -> BaseHardwareController: ...

def load_yaml_file(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise RuntimeError(f"YAML file not found: {path}")
    except yaml.YAMLError as e:
        raise RuntimeError(f"Invalid YAML in {path}: {e}")

    if data is None:
        return {}  # or raise, depending on your needs

    return data


logger = RcutilsLogger('HW-mng supervisor')

def import_class(path: str) -> type:
    try:
        modulename, classname = path.split(":")
    except ValueError as e:
        raise RuntimeError(f"Invalid class path '{path}', use 'path.to.module:class' syntax.")
    
    module = import_module(modulename)
    try:
        _class = getattr(module, classname)
    except AttributeError:
        raise RuntimeError(f"class '{classname}' not found in module {module}")
    
    return _class
    

def import_module(path: str) -> ModuleType | None:
    """ Attempts import of hardare controller module at runtime """
    # NOTE for now this only works with a symlink install
    try:
        hw_controller_class = importlib.import_module(path)
        return hw_controller_class
    
    except Exception as e:
        raise RuntimeError(f"Failed to import hardware controller '{path}': {e}.")


def main(args=None):
    # simulate CLI input
    INPUT_CONFIG = "teodore"
    YAML_FILE = "src/hardware_mng/hardware_mng/hw_configurations.yaml"
    STRICT_MODE = True #wheter to stop if any of the controllers fail to load

    import os
    logger.info(f"Beginning hardare manager system initialization. CWD: {os.getcwd()}")

    try:
        config_data: dict[str, list[str]] = load_yaml_file(YAML_FILE)
    except RuntimeError as e:
        logger.fatal(f"Failed to load Hardwdare Configuration file -> {e}")
        exit(-1)
    
    hw_controllers_paths: list[str] | None = config_data.get(INPUT_CONFIG)
    if hw_controllers_paths is None:
        logger.fatal(f"Configuration '{INPUT_CONFIG}' not found in hardware configuration file at '{YAML_FILE}'")
        exit(-1)

    controllers: list[BaseHardwareController] = []

    for path in hw_controllers_paths:
        try:
            class_obj: ControllerClass = import_class(path)
        except RuntimeError as e:
            logger.warning(f"Failed to load hw controller at {path} -> {e}")
            continue

        try:
            controller = class_obj()
        except Exception as e:
            logger.warning(f"Failed to instantiate hw controller at '{path}' -> {e}")
            continue
        
        logger.info(f"Succesfully loaded and instantiated hw controller at '{path}'")
        controllers.append(controller)
    
    ok = len(controllers)
    total = len(hw_controllers_paths)
    if ok == total:
        logger.info(f"Succesfully loaded {ok}/{ok} hw controllers from configuration {INPUT_CONFIG}")
    elif not STRICT_MODE:
        logger.warning(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded. The hardware may not work completely.")
    else:
        logger.fatal(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded, shutting down.")
        exit(-1)

    exit()
    # let cfg configure dispatcher
    dispatcher: Dispatcher[int, float] = Dispatcher()
    cfg.configure_dispatcher(dispatcher)

    # let cfg configure batch dispatcher
    batch_dispatcher: BatchDispatcher[int, float] = BatchDispatcher(dispatcher)
    cfg.configure_batch_dispatcher(batch_dispatcher)
    
    # creates loopers (for flushing hardware)
    looper = LoopSupervisor()
    for driver in cfg.get_drivers():
        looper.add_loop(driver.loop_freq, driver.driver.flush)

    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(batch_dispatcher, looper)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
