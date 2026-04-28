from typing import List, Dict
import time

class Subscriber:
    def __init__(self):
        self.messages = []
    
    def read(self):
        while len(self.messages) > 0:
            yield self.messages.pop()

class Publisher:
    def __init__(self):
        self.subscribers: List[Subscriber] = []
    
    def _add_subscriber(self, sub: Subscriber):
        self.subscribers.append(sub)

    def publish(self, msg):
        for sub in self.subscribers:
            sub.messages.append(msg)


class BehaviorContext:
    """
    Shared interface passed to all behaviors.

    The default context implements ways for a behavior to exchange data
    with other behaviors.

    This should abstract interaction with the outside system
    (logging, messaging, robot APIs, etc.).
    """

    def __init__(self):
        self._sync_time = 0.0
        self._publishers: Dict[str, Publisher] = {}

    @property
    def time(self) -> float:
        """
        Returns elapsed time (syncronized with all other behaviours)
        """
        return self._sync_time

    def get_time(self):
        """
        Computes exact time from time.monotonic()
        """
        return time.monotonic()

    def create_subscriber(self, topic: str) -> Subscriber:
        sub = Subscriber()
        pub = self.create_publisher(topic)
        pub._add_subscriber(sub)
        return sub

    def create_publisher(self, topic: str) -> Publisher:
        if topic not in self._publishers:
            self._publishers[topic] = Publisher()
        return self._publishers[topic]