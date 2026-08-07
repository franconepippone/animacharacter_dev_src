# ros_async_utils.py

from __future__ import annotations

from typing import Awaitable, Callable, Any, TypeVar, cast

from rclpy.timer import Timer
from rclpy.node import Node
from rclpy.executors import Executor
from rclpy.task import Future
from rclpy.callback_groups import ReentrantCallbackGroup, CallbackGroup

T = TypeVar("T")

cb_group = ReentrantCallbackGroup()


class BetterAsyncNode(Node):
    """
    A subclass of rclpy.node.Node that provides async utilities for ROS 2.
    """

    async def asleep(self, seconds: float) -> None:
        future = Future()
        timer: Timer | None = None

        def wakeup():
            if not future.done():
                future.set_result(None)

        timer = self.create_timer(seconds, wakeup, callback_group=cb_group)

        try:
            await future
        finally:
            if timer is not None:
                self.destroy_timer(timer)

    async def agather(self, *coroutines: Awaitable[T], executor: Executor | None = None) -> tuple[T]:
        """
        Schedule multiple coroutines on a rclpy executor and wait for all.
        """
        if executor is None:
            executor = self.executor
            if executor is None:
                raise RuntimeError("No executor provided and node has no executor.")

        tasks = [
            executor.create_task(coro) # type: ignore
            for coro in coroutines
        ]

        results = []
        for task in tasks:
            results.append(await task)

        return tuple(results)

    def create_one_shot_timer(
                self,
                delay: float,
                callback: Callable[[], Any],
                callback_group: CallbackGroup | None = None
            ) -> Timer:
            timer: Timer
    
            async def wrapped_callback():
                self.destroy_timer(timer)
                await callback()
    
            # NOTE this is unfortunately needed because the stubs/api annotations 
            # in rclpy raise typing errors when passing coros as callbacks
            type_forced_cb = cast(
                Callable[..., Any],
                wrapped_callback
            )

            if callback_group is None:
                callback_group = cb_group
    
            timer = self.create_timer(delay, type_forced_cb, callback_group)
    
            return timer