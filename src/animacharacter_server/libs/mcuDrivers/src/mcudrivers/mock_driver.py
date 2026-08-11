from typing import Dict
from threading import RLock

from .base_driver import BaseHardwareDriver, GenericLogger

import random
import time

class MockDriver(BaseHardwareDriver):
    """A versitile placeholder driver"""

    def __init__(self, logger: GenericLogger) -> None:
        super().__init__()
        self.logger = logger
        self.axes_state: Dict[str, float] = {}
        self.count = 0
        self.dirty = False
        self.lock = RLock()

    def deinit(self) -> bool:
        self.logger.warning("deinit")
        return True

    def begin(self) -> bool:
        self.logger.info("Beginning")
        return True
    
    def get_batch_lock(self) -> RLock:
        return self.lock
    
    def write_axis(self, name: str, value: float):
        self.dirty = True
        with self.lock:
            self.axes_state[name] = value
            self.logger.info(f"Wrote {name}:{value:.2f}")
    
    def flush(self) -> bool:
        if self.dirty:
            with self.lock:
                self.logger.info(f"flushing [{self.count}]")
                self.count += 1

            # simulate io
            time.sleep(random.random() * 0.01)
        self.dirty = False
        return True
        