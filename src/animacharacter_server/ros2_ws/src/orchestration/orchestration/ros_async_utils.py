# ros_async_utils.py

from __future__ import annotations

from typing import Awaitable, Iterable, TypeVar

from rclpy.timer import Timer
from rclpy.node import Node
from rclpy.executors import Executor
from rclpy.task import Future
from rclpy.callback_groups import ReentrantCallbackGroup

T = TypeVar("T")


cb_group = ReentrantCallbackGroup()

async def sleep(node: Node, seconds: float) -> None:
    future = Future()
    timer: Timer | None = None

    def wakeup():
        if not future.done():
            future.set_result(None)

    timer = node.create_timer(seconds, wakeup, callback_group=cb_group)

    try:
        await future
    finally:
        if timer is not None:
            node.destroy_timer(timer)

async def gather(executor: Executor, *coroutines: Awaitable[T]) -> tuple[T]:
    """
    Schedule multiple coroutines on a rclpy executor and wait for all.
    """
    tasks = [
        executor.create_task(coro) # type: ignore[arg-type]
        for coro in coroutines
    ]

    results = []
    for task in tasks:
        results.append(await task)

    return tuple(results)