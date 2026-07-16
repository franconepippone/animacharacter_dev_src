"""
Helper module for runtime plugin parsing / loading.

"""


from typing import Type
from types import ModuleType
import importlib
import sys
import yaml
import os

def last_existing_path(paths):
    """
    Returns the last existing file path from the given list.
    If none exist, returns an empty string.
    """
    for path in reversed(paths):
        if os.path.exists(path):
            return path
    return ""

def register_plugin_dirs(plugin_dirs: list[str]) -> None:
    """ Adds list of directories to sys.path so python can imports the modules contained in them """
    for d in plugin_dirs:
        if d not in sys.path:
            sys.path.insert(0, d)

def load_yaml_file(path: str) -> dict:
    """ Loads a yaml file """
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


def import_class(path: str) -> Type:
    """ Imports class from module at runtime """
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
    """ Attempts import of module at runtime """
    # NOTE for now this only works with a symlink install
    try:
        hw_controller_class = importlib.import_module(path)
        return hw_controller_class
    
    except Exception as e:
        raise RuntimeError(f"Failed to import hardware controller '{path}': {e}.")
