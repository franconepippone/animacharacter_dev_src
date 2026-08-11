
import inspect
from typing import get_type_hints


def get_first_argument_type(func):
    """
    Return the type annotation of the first argument after `self` (if present).
    Considers both positional and keyword-only arguments.
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    params = list(sig.parameters.values())

    # Skip self / cls if present
    if params and params[0].name in ("self", "cls"):
        params = params[1:]

    for param in params:
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return hints.get(param.name)

    return None


def flatten_dict(data, parent_key="", sep="/"):
    flat = {}

    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key

        if isinstance(value, dict):
            flat.update(flatten_dict(value, new_key, sep))
        else:
            flat[new_key] = value

    return flat


def flatten_for_diagnostics(data, parent_key="", sep="/", max_depth=10, _depth=0):
    """
    Flattens nested dict/list structures into ROS diagnostic-safe key/value pairs.

    Rules:
    - keys become strings with '/' separators
    - all values become strings
    - lists are indexed: key/0, key/1, ...
    - None values are preserved as "None" (or can be skipped if desired)
    """

    flat = {}

    if _depth > max_depth:
        flat[parent_key] = str(data)
        return flat

    # dict case
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            flat.update(
                flatten_for_diagnostics(v, new_key, sep, max_depth, _depth + 1)
            )

    # list / tuple / set case
    elif isinstance(data, (list, tuple, set)):
        for i, v in enumerate(data):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            flat.update(
                flatten_for_diagnostics(v, new_key, sep, max_depth, _depth + 1)
            )

    # leaf node
    else:
        key = parent_key if parent_key else "value"

        if data is None:
            flat[key] = "None"
        elif isinstance(data, bool):
            flat[key] = "true" if data else "false"
        else:
            flat[key] = str(data)

    return flat