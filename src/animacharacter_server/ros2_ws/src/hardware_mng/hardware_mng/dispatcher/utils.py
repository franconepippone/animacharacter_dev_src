from typing import Optional, Callable, Any

class HooksContext:
    """
    Reusable context manager that calls optional pre/post hooks.
    
    Each instance can be used multiple times in `with` statements.
    """
    def __init__(self, pre_hook: Optional[Callable[[], Any]] = None,
                       post_hook: Optional[Callable[[], Any]] = None):
        self.pre_hook = pre_hook
        self.post_hook = post_hook

    def __enter__(self):
        if self.pre_hook:
            self.pre_hook()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.post_hook:
            self.post_hook()
        return False  # Do not suppress exceptions
