import time
import threading
import pytest

import rclpy
from rclpy.task import Future
from rclpy.executors import MultiThreadedExecutor

from orchestration.ros_async_utils import (
    BetterAsyncNode,
    asleep,
    agather,
    create_one_shot_timer,
    wait_future,
)


# --- Fixtures ---
@pytest.fixture(scope="module")
def rclpy_init_shutdown():
    # ensure rclpy is initialized for the test module
    initialized = False
    if not rclpy.ok():
        rclpy.init()
        initialized = True
    yield
    if initialized and rclpy.ok():
        rclpy.shutdown()


@pytest.fixture()
def executor_thread(rclpy_init_shutdown):
    executor = MultiThreadedExecutor()
    stop_evt = threading.Event()

    def spin():
        while not stop_evt.is_set():
            try:
                executor.spin_once(timeout_sec=0.05)
            except Exception:
                # Keep the spin loop alive; let test assertions observe errors.
                continue

    t = threading.Thread(target=spin, daemon=True)
    t.start()

    yield executor

    stop_evt.set()
    t.join(timeout=2.0)


@pytest.fixture()
def node(executor_thread):
    node = BetterAsyncNode('test_node')
    executor_thread.add_node(node)
    try:
        yield node
    finally:
        try:
            executor_thread.remove_node(node)
        except Exception:
            pass
        try:
            node.destroy_node()
        except Exception:
            pass


# --- Helpers ---

def wait_for_task_result(task, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if task.done():
            exc = task.exception()
            if exc:
                raise exc
            return task.result()
        time.sleep(0.01)
    raise TimeoutError("Task did not complete in time")


# --- Tests (NO asyncio; use ROS executor tasks) ---

def test_asleep_basic(node, executor_thread):
    start = time.monotonic()
    task = executor_thread.create_task(node.asleep(0.12))
    wait_for_task_result(task, timeout=2.0)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.11, f"asleep returned too early: {elapsed}"


def test_asleep_concurrent(node, executor_thread):
    tasks = [executor_thread.create_task(node.asleep(0.05 * i)) for i in range(1, 5)]
    for t in tasks:
        wait_for_task_result(t, timeout=2.0)


def test_wait_future_success(node, executor_thread):
    fut = Future()

    def set_result_cb():
        if not fut.done():
            fut.set_result('ok')

    timer = node.create_timer(0.05, set_result_cb)

    try:
        task = executor_thread.create_task(wait_future(node, fut, timeout=1.0))
        res = wait_for_task_result(task, timeout=2.0)
        assert res == 'ok'
    finally:
        node.destroy_timer(timer)


def test_wait_future_timeout_returns_none(node, executor_thread):
    fut = Future()
    task = executor_thread.create_task(wait_future(node, fut, timeout=0.08))
    res = wait_for_task_result(task, timeout=2.0)
    assert res is None


def test_wait_future_exception_propagates(node, executor_thread):
    fut = Future()

    def set_exc_cb():
        if not fut.done():
            fut.set_exception(RuntimeError('boom'))

    timer = node.create_timer(0.05, set_exc_cb)

    try:
        task = executor_thread.create_task(wait_future(node, fut, timeout=1.0))
        with pytest.raises(RuntimeError):
            wait_for_task_result(task, timeout=2.0)
    finally:
        node.destroy_timer(timer)


def test_wait_future_invalid_timeout_raises(node, executor_thread):
    fut = Future()
    task = executor_thread.create_task(wait_future(node, fut, timeout=0))
    with pytest.raises(ValueError):
        wait_for_task_result(task, timeout=1.0)


def test_agather_multiple_coroutines(node, executor_thread):
    async def work(i: int):
        await node.asleep(0.02 * i)
        return i * 2

    task = executor_thread.create_task(node.agather(work(3), work(1), work(2)))
    res = wait_for_task_result(task, timeout=3.0)
    assert set(res) == {2, 4, 6}


def test_create_one_shot_timer_invokes_callback_once(node, executor_thread):
    called = threading.Event()

    async def cb():
        called.set()

    timer = node.create_one_shot_timer(0.05, cb)

    assert called.wait(timeout=2.0), "one-shot callback not invoked"

    # allow a short time and ensure callback isn't invoked twice
    called.clear()
    time.sleep(0.2)
    assert not called.is_set(), "one-shot callback invoked multiple times"


def test_agather_handles_exceptions(node, executor_thread):
    async def ok():
        await node.asleep(0.01)
        return 'ok'

    async def fail():
        await node.asleep(0.01)
        raise ValueError('fail')

    task = executor_thread.create_task(node.agather(ok(), fail()))
    with pytest.raises(ValueError):
        wait_for_task_result(task, timeout=3.0)


def test_stress_many_concurrent(node, executor_thread):
    async def small(i):
        await node.asleep(0.01)
        return i

    coros = [small(i) for i in range(40)]
    task = executor_thread.create_task(node.agather(*coros))
    results = wait_for_task_result(task, timeout=10.0)
    assert len(results) == 40
    assert set(results) == set(range(40))


def test_asleep_while_shutdown(rclpy_init_shutdown):
    # create a local node outside executor and cancel it quickly
    node_local = BetterAsyncNode('temp_node')
    executor = MultiThreadedExecutor()
    executor.add_node(node_local)
    stop_evt = threading.Event()

    def spin_once():
        while not stop_evt.is_set():
            try:
                executor.spin_once(timeout_sec=0.02)
            except Exception:
                continue

    t = threading.Thread(target=spin_once, daemon=True)
    t.start()

    try:
        task = executor.create_task(node_local.asleep(0.5))
        # give it a moment then shutdown rclpy
        time.sleep(0.05)
        rclpy.shutdown()

        # wait for task to complete (best-effort)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if task.done():
                break
            time.sleep(0.01)
    finally:
        stop_evt.set()
        t.join(timeout=1.0)
        try:
            executor.remove_node(node_local)
        except Exception:
            pass
        try:
            node_local.destroy_node()
        except Exception:
            pass
