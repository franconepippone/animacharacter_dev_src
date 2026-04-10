"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
from typing import Protocol
from types import ModuleType
import importlib
import rclpy
from rclpy.logging import RcutilsLogger

from .abstract_hw_controller import BaseHardwareController, MotionCommand
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher
from .looper import LoopSupervisor, LoopDescriptor

import yaml


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


logger = RcutilsLogger('HW-mng starter')

def import_class(path: str) -> type:
    try:
        modulename, classname = path.split(":")
    except ValueError as e:
        raise RuntimeError(f"Invalid class path '{path}', use 'path.to.module:class' syntax.")
    
    module = import_module(modulename)
    try:
        _class = getattr(module, classname)
    except AttributeError:
        raise RuntimeError(f"class '{classname}' not found in module {modulename}")
    
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
    INPUT_CONFIG = "testing"
    YAML_FILE = "src/hardware_mng/hardware_mng/hw_configurations.yaml"
    STRICT_MODE = True #wheter to stop if any of the controllers fail to load

    import os
    logger.info(f"Beginning hardare manager system initialization. CWD: {os.getcwd()}")

    # loading configs
    try:
        config_data: dict[str, list[str]] = load_yaml_file(YAML_FILE)
    except RuntimeError as e:
        logger.fatal(f"Failed to load Hardwdare Configuration file -> {e}")
        exit(-1)
    
    hw_controllers_paths: list[str] | None = config_data.get(INPUT_CONFIG)
    if hw_controllers_paths is None:
        logger.fatal(f"Configuration '{INPUT_CONFIG}' not found in hardware configuration file at '{YAML_FILE}'")
        exit(-1)

    total = len(hw_controllers_paths)

    controllers: list[BaseHardwareController] = []

    # building controllers
    for i, path in enumerate(hw_controllers_paths):
        try:
            class_obj: ControllerClass = import_class(path)
        except RuntimeError as e:
            logger.warning(f"[{i+1}/{total}] Failed to load hw controller at '{path}' -> {e}")
            continue

        try:
            controller = class_obj()
        except Exception as e:
            logger.warning(f"[{i+1}/{total}] Failed to instantiate hw controller at '{path}' -> {e}")
            continue
        
        logger.info(f"[{i+1}/{total}] loaded and instantiated hw controller at '{path}'")
        controllers.append(controller)
    
    ok = len(controllers)
    if ok == total:
        logger.info(f"Succesfully loaded {ok}/{ok} hw controllers from configuration '{INPUT_CONFIG}'")
    elif not STRICT_MODE:
        logger.warning(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded. The hardware may not work completely.")
    else:
        logger.fatal(f"Only {ok}/{total} hw controllers from configuration '{INPUT_CONFIG}' could be loaded, shutting down.")
        exit(-1)

    # configure the dispatcher and looper
    looper = LoopSupervisor()
    dispatcher: Dispatcher[int, MotionCommand] = Dispatcher()
    
    loop_ctrl_pairs: list[tuple[LoopDescriptor, BaseHardwareController]] = []

    for ctrl in controllers:
        loop = looper.add_loop(f"loop-{ctrl.name}", ctrl.flush_freq, ctrl._flush, start_now=False)    
        # make it so every received commmand with a command_group id gets put in the correct input queue.
        handler = lambda cmd: loop.input_queue.put(cmd, block=False)
        for id in ctrl.command_group:
            dispatcher.register_handler(id, handler)
        
        # keep the loop and respective controller boundled together in this tuple
        loop_ctrl_pairs.append((loop, ctrl))

    logger.info("Configuration complete, starting ros node.")
    
    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(dispatcher, looper, loop_ctrl_pairs)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
