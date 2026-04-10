from .base_driver import BaseHardwareDriver
from threading import RLock


class ThreadSafeDriver:
    def __init__(self, driver: BaseHardwareDriver):
        self.driver = driver