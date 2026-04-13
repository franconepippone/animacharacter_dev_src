"""Threaded loop management utility.

Provides LoopSupervisor class for managing multiple concurrent loops at specified
frequencies. Each loop runs in its own daemon thread and can be individually
paused, resumed, or stopped.

Example:
    looper = LoopSupervisor()
    loop_desc = looper.add_loop(freq=10, job=my_callback, start_now=True)
    # ...
    looper.stop_all(block=True)
"""
from __future__ import annotations
from typing import Callable, Optional, Any, Dict, Iterable, ContextManager
from dataclasses import dataclass
import threading as th
from queue import Queue
import time
from enum import Enum, auto

from rclpy.logging import RcutilsLogger


class LoopAction(Enum):
    """Pass a value of this enum to the constructor of LoopActionRequest"""
    PAUSE = auto()
    STOP = auto()

@dataclass
class LoopActionRequest:
    """Raise this inside a lop job function to perform either PAUSE/STOP a loop from the inside."""
    action: LoopAction

def _loop(
    descriptor: LoopDescriptor,
    ):
    """Generic loop function executed in a separate thread.
    
    Args:
        descriptor: LoopDescriptor with all loop configuration and state.
    """
    while descriptor._run.is_set():
        iteration_start = time.perf_counter()
        
        # if wait is false, blocks until it is true (paused)
        descriptor._wait.wait()
        try:
            with descriptor.context:
                result: Optional[LoopActionRequest] = descriptor.job(descriptor.input_queue, descriptor.output_queue)

            # job can optionally return a request to perform an action
            if isinstance(result, LoopActionRequest):
                if result.action == LoopAction.PAUSE:
                    descriptor._wait.clear() # pauses on next iteration
                elif result.action == LoopAction.STOP:
                    # this should match what _request_loop_stop does below
                    descriptor._run.clear()
                    descriptor._wait.set()
                    return # not necessary

        except Exception as e:
            # run exception handler if set
            if descriptor.exception_cb: descriptor.exception_cb(e)

        if not descriptor._run.is_set(): return # exit early if this is already true

        # sleep for remaining time in the period
        elapsed = time.perf_counter() - iteration_start
        sleep_time = descriptor.period - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

class EmptyContextManager:
    def __enter__(self):
        return None
    def __exit__(self, exc_type, exc, tb):
        return False


type LoopJob = Callable[[Queue, Queue], None | LoopActionRequest]

@dataclass
class LoopDescriptor:
    """Describes a registered loop task.
    
    Attributes:
        id (int): Unique identifier for this loop.
        input_queue (Queue): Optional queue for sending consumable data to the job.
        output_queue (Queue): Optional queue for receiving processed data from the job.
        context (ContextManager): Context manager for the job (e.g. a threading.Lock for thread safe operation)
        freq (float): Loop frequency in Hz.
        period (float): Loop period in seconds.
        is_running (bool): True if thread exists and is running.
        job (Callable[[Queue, Queue], Any]): Callback function executed each iteration. Receives input and output queues as arguments, can be used for inter-thread communication.
        exception_cb (Callable[[Exception], Any]): If present, when job raises an exception this will be called with that exception as argument.
        _wait (threading.Event): PRIVATE - Event for pause control (cleared to pause, set to resume).
        _run (threading.Event): PRIVATE - Event that controls if loop continues (cleared to stop).
        _thread (threading.Thread): PRIVATE - Thread object running the loop (None if not started).
    """
    name: str
    id: int
    input_queue: Queue
    output_queue: Queue
    _run: th.Event
    _wait: th.Event
    context: ContextManager
    freq: float
    job: LoopJob
    _thread: th.Thread | None = None
    exception_cb: Callable[[Exception], Any] | None = None

    @property
    def is_running(self) -> bool:
        """Check if the loop thread is currently running."""
        if self._thread is None:
            return False
        return self._thread.is_alive()
    
    @property
    def period(self) -> float:
        """Period between loop iterations (seconds)."""
        return 1 / self.freq

class LoopSupervisor:
    """Helps managing multiple concurrent (threaded) loops, each running at a specified frequency.
    
    Each loop is represented by a LoopDescriptor dataclass, which is returned after a call to
    the methods 'add_loop' or 'get_loop_from_id/get_loops'. This object is ment for inspection only,
    it's content should never be modified manually.

    NOTE that this class relies on time.sleep and time.perf_counter for timing, so
    there might be substantial jitter in the loops, depending on OS, expecially at high frequencies.

    Baseline working:
    - Each loop runs in its own daemon thread
    - Loops can be paused/resumed individually
    - Exceptions can be handled by assigning a custom callback
    - When creating loops, a shared lock can be given for Thread-safe operations.
    """
    def __init__(self, logger_name: str = 'LoopSupervisor'):
        """Initialize the LoopSupervisor."""
        self.logger = RcutilsLogger(logger_name)
        self.loop_pool: Dict[int, LoopDescriptor] = {}
        self.id_counter = 0
    
    def _add_loop_to_pool(self, l: LoopDescriptor):
        self.loop_pool[l.id] = l
    
    def _start_loop(self, desc: LoopDescriptor, paused: bool) -> bool:
        """Start a loop thread.
        
        Args:
            desc: LoopDescriptor to start.
        
        Returns:
            True if thread started successfully, False otherwise.
        """
        if desc.is_running:
            # cannot start a thread if the old one is still running
            return False

        # creates a brand new thread
        desc._thread = th.Thread(target=_loop, args=(desc,), daemon=True)
        desc._run.set()
        desc._wait.set() if not paused else desc._wait.clear()
        try:
            desc._thread.start()
        except (RuntimeError, SystemError, OSError) as e:
            self.logger.error(f"Could not start thread for loop id={desc.id}: {e}")
            return False
        return True

    def _request_loop_stop(self, desc: LoopDescriptor):
        if not desc.is_running: return
        desc._run.clear()
        desc._wait.set()
    
    def _get_new_id(self) -> int:
        """Generate a new valid id."""
        self.id_counter += 1
        return self.id_counter
    
    def _set_loop_paused(self, paused: bool, desc: LoopDescriptor):
        desc._wait.clear() if paused else desc._wait.set()

    # public interface

    def is_paused(self, loop_id: int) -> bool:
        if loop := self.get_loop_from_id(loop_id):
            return not loop._wait.is_set()
        return False

    def pause_all(self):
        for loop in self.get_loops():
            self._set_loop_paused(True, loop)
    
    def resume_all(self):
        for loop in self.get_loops():
            self._set_loop_paused(False, loop)

    def stop_all(self, block: bool = True, timeout: float = 1.0):
        """Stop all running loops.

        Args:
            block (bool): If True, block until all loops have stopped.
            timeout (float): Maximum time to wait **PER** loop. With multiple loops,
                the total wait time can reach timeout * N_loops in the worst case.
        """

        for loop in self.loop_pool.values():
            self._request_loop_stop(loop)
        
        if block:
            for loop in self.loop_pool.values():
                if loop._thread is not None:
                    loop._thread.join(timeout=timeout)

    def stop_loop(self, loop_id: int, block: bool = True, timeout: float = 1.0) -> bool:
        """Stop a specific loop.
        
        Args:
            loop_id (int): ID of the loop to stop.
            block (bool): If True (default), blocks until the loop stops.
            timeout (float): maximum time this method can block
        """
        if loop := self.get_loop_from_id(loop_id):
            self._request_loop_stop(loop)
            if block and loop._thread is not None:
                loop._thread.join(timeout=timeout)
            return not loop.is_running
        return False

    def pause_loop(self, loop_id: int) -> bool:
        """Pause a specific loop without stopping it.
        
        Args:
            loop_id: ID of the loop to pause.
        Returns:
            False if loop is not found.
        """
        if loop := self.get_loop_from_id(loop_id):
            loop._wait.clear()
            return True
        return False
    
    def resume_loop(self, loop_id: int) -> bool:
        """Resume a paused loop.
        
        Args:
            loop_id: ID of the loop to resume.
        Returns:
            False if loop is not found.
        """
        if loop := self.get_loop_from_id(loop_id):        
            loop._wait.set()
            return True
        return False

    def get_loop_from_id(self, id: int) -> LoopDescriptor | None:
        """Get loop descriptor by ID.
        
        Args:
            id (int): Loop ID.
        
        Returns:
            LoopDescriptor if found, None otherwise.
        """
        return self.loop_pool.get(id, None)
    
    def get_loops(self) -> Iterable[LoopDescriptor]:
        """Get all registered loops.
        
        Returns:
            Iterable of all LoopDescriptors.
        """
        return self.loop_pool.values()

    def all_running(self) -> bool:
        """Returns true if all registered loops are running"""
        if not self.loop_pool:
            return False
        return all([loop.is_running for loop in self.loop_pool.values()])

    def all_stopped(self) -> bool:
        """Returns true if all registered loops are stopped"""
        if not self.loop_pool: return False
        return not any([loop.is_running for loop in self.loop_pool.values()])

    def start_all(self, paused: bool = False):
        """Start all registered loops."""
        for loop in self.loop_pool.values():
            self._start_loop(loop, paused)

    def start_loop(self, loop_id: int, paused: bool = False) -> bool:
        """Starts a loop from it's id.
        
        Returns:
            True if succesfull
        """
        if loop := self.get_loop_from_id(loop_id):
            return self._start_loop(loop, paused)
        return False

    def add_loop(
        self,
        name: str, 
        freq: float, 
        job: LoopJob,
        start_now: bool = False,
        context_manager: ContextManager | None = None,
        exception_handler: Callable[[Exception], Any] | None = None
    ) -> LoopDescriptor:
        """Register a new loop task.
        
        Args:
            freq: Loop frequency in Hz (must be > 0).
            job: Callable to execute each iteration.
            start_now: If True, start the loop immediately.
            context_manager: Custom ContextManager (e.g. Lock) for job.
            exception_handler: If given, exceptions raised by 'job' during loop can be processed here.

        Returns:
            LoopDescriptor for the created loop.
        
        Raises:
            ValueError: If freq <= 0.
        """
        if freq <= 0:
            raise ValueError(f"Frequency must be positive, got {freq}")
        
        # create events / locks objects if not given
        run_evnt = th.Event()
        wait_evnt = th.Event()
        context = EmptyContextManager() if context_manager is None else context_manager

        loop_id = self._get_new_id()

        descriptor = LoopDescriptor(
            name=name,
            id=loop_id,
            input_queue=Queue(),
            output_queue=Queue(),
            _run=run_evnt,
            _wait=wait_evnt,
            context=context,
            freq=freq,
            job=job,
            _thread=None,
            exception_cb=exception_handler
        )

        self._add_loop_to_pool(descriptor)
        if start_now:
            self._start_loop(descriptor, paused=False)
        
        return descriptor

    def get_loop_status_json(self, l: LoopDescriptor):
        def loop_state(l: LoopDescriptor) -> str:
            if not l._thread:
                return "NOT STARTED"
            if not l.is_running:
                return "STOPPED"
            return "RUNNING" if l._wait.is_set() else "PAUSED"

        return  {
                "name" : l.name,
                "id": l.id,
                "state": loop_state(l),
                "freq": l.freq,
                "is_running": l.is_running,
                "ctx_manager": type(l.context).__name__,
                "exception_cb": l.exception_cb is not None
            }


    def status_as_json(self) -> dict:
        """
        Return a structured dictionary with all loop status data.
        """
        loops = sorted(self.loop_pool.values(), key=lambda l: l.id)

        running = sum(l.is_running and l._wait.is_set() for l in loops)
        paused = sum(l.is_running and not l._wait.is_set() for l in loops)
        stopped = len(loops) - running - paused

        loops_data = {}
        for l in loops:
            loops_data[l.id] = self.get_loop_status_json(l)

        return {
            "total": len(loops),
            "running": running,
            "paused": paused,
            "stopped": stopped,
            "loops": loops_data
        }


if __name__ == "__main__":

    def job1(input, output): print("hello1")
    def job2(input, output): print("hello2")
    looper = LoopSupervisor()
    l1 = looper.add_loop("pipo", 1, job1)
    l2 = looper.add_loop("pino", 2, job2)

    looper.start_all()

    ok = looper.all_running()

    print(ok)

    time.sleep(1)
    print("pausing loop 1")
    looper.pause_loop(l1.id)
    time.sleep(3)
    print("resuming loop 1")
    looper.resume_loop(l1.id)

    time.sleep(1)
    print("stopping loop2")
    looper.stop_loop(l2.id)

    print("all running:", looper.all_running())
    time.sleep(2)
    looper.stop_all()

    if l1._thread:
        l1._thread.join()