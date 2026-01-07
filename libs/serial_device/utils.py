from __future__ import annotations
from time import sleep, time


def poll(timeout: float, interval: float):
    """
    Generator for polling at a given interval with a given timeout.
    See poller.py for usage example.
    
    NOTE: This right now uses fixed sleep. It can be made more accurate by measuring timings instead
    
    :param timeout: timeout in seconds
    :type timeout: float
    :param interval: polling interval in seconds
    :type interval: float
    """
    loops_max = int(timeout / interval)
    for i in range(loops_max):
        yield i * interval
        sleep(interval)


class Timer:
    '''
    Can be started with start(secs), check() returns true when 'secs' seconds
    have passed since the last call to start()
    '''
    fire_time: float = 0
    
    def __init__(self, time_secs: float) -> None:
        self.time_secs = time_secs

    def start(self, time_secs: float | None = None) -> Timer:
        time_secs = time_secs if time_secs else self.time_secs
        self.fire_time = time_secs + time()
        return self

    def timed_out(self) -> bool:
        """
        Checks wheter the timer has timeout out or not

        :return: If 
        :rtype: bool
        """
        return time() >= self.fire_time


if __name__ == "__main__":
    for i in poll(5, .5):
        print(i)