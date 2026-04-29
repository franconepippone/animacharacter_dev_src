from typing import List, Dict
import time
from collections import deque

class Subscriber:
    """
    A message subscriber in a behavior running context.
    Use 'pull()' to get all the latest messages.

    Do not instantiate this direclty, use 'create_subscriber()' from the context.
    """
    def __init__(self):
        self._messages = deque()
    
    def clear(self):
        """
        Clears all received messages.
        """
        self._messages.clear()

    def pull(self):
        """
        Returns an iterator of all received messages since last call.
        """
        while len(self._messages) > 0:
            yield self._messages.popleft()

class Publisher:
    """
    A message publisher in a behavior running context.
    Use 'publish()' to publish messages.

    Do not instantiate this direclty, use 'create_publisher()' from the context.
    """
    def __init__(self):
        self._subscribers: List[Subscriber] = []
    
    def _add_subscriber(self, sub: Subscriber):
        self._subscribers.append(sub)

    def publish(self, msg):
        """
        Publish a message on this topic. All subscribers will receive it.
        """
        for sub in self._subscribers:
            sub._messages.append(msg)


class BehaviorContext:
    """
    Shared interface passed to all behaviors.

    The default context implements ways for a behavior to exchange data
    with other behaviors.

    Subclass this to abstract interaction with the outside system
    (logging, messaging, robot APIs, etc.).
    """

    class time:
        """
        Utility static class for time management
        """
        _sync_time: float = 0.0

        @classmethod
        def time(cls):
            """
            Returns elapsed time (syncronized with all other behaviours)
            """
            return cls._sync_time
        
        @staticmethod
        def get_time():
            """
            Computes exact time from time.monotonic()
            """
            return time.monotonic()

    def __init__(self):
        self._publishers: Dict[str, Publisher] = {}

    def create_subscriber(self, topic: str) -> Subscriber:
        """Creates a new subscriber for a topic. If the topic doesn't exist, it will be created."""
        sub = Subscriber()
        pub = self.create_publisher(topic)
        pub._add_subscriber(sub)
        return sub

    def create_publisher(self, topic: str) -> Publisher:
        """Creates a new publisher for a topic. If the topic doesn't exist, it will be created."""
        if topic not in self._publishers:
            self._publishers[topic] = Publisher()
        return self._publishers[topic]