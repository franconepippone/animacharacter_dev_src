from __future__ import annotations

from typing import Awaitable, Callable, Any, TypeVar, cast

from rclpy.timer import Timer
from rclpy.node import Node
from rclpy.executors import Executor
from rclpy.task import Future
from rclpy.callback_groups import ReentrantCallbackGroup, CallbackGroup


T = TypeVar("T")

cb_group = ReentrantCallbackGroup()



### CONSIDER THIS METHOD OF PERFORMING BLOCKING WAITS

##def call(
#        self,
#        request: SrvRequestT,
#        timeout_sec: Optional[float] = None
#    ) -> Optional[SrvResponseT]:
#        """
#        Make a service request and wait for the result.
#
#        .. warning:: Do not call this method in a callback, or a deadlock or timeout may occur.
#
#        :param request: The service request.
#        :param timeout_sec: Seconds to wait. If ``None``, then wait forever.
#        :return: The service response.
#        :raises: TypeError if the type of the passed request isn't an instance
#          of the Request type of the provided service when the client was
#          constructed.
#        :raises: TimeoutError if the response is not available within the timeout.
#        """
#        if not isinstance(request, self.srv_type.Request):
#            raise TypeError()
#
#        event = threading.Event()
#
#        def unblock(future: Future[SrvResponseT]) -> None:
#            nonlocal event
#            event.set()
#
#        future = self.call_async(request)
#        future.add_done_callback(unblock)
#
#        # Check future.done() before waiting on the event.
#        # The callback might have been added after the future is completed,
#        # resulting in the event never being set.
#        if not future.done():
#            if not event.wait(timeout_sec):
#                # Timed out. remove_pending_request() to free resources
#                self.remove_pending_request(future)
#                raise TimeoutError()
#
#        exception = future.exception()
#        if exception is not None:
#            raise exception
#        return future.result()

async def asleep(
    node: Node,
    seconds: float,
) -> None:
    future: Future[None] = Future()

    def wakeup() -> None:
        if not future.done():
            future.set_result(None)

    timer = node.create_timer(
        seconds,
        wakeup,
        callback_group=cb_group,
    )

    try:
        await future
    finally:
        node.destroy_timer(timer)


async def agather(
    node: Node,
    *coroutines: Awaitable[T],
    executor: Executor | None = None,
) -> tuple[T, ...]:
    """
    Schedule multiple coroutines on a rclpy executor and wait for all.
    """
    if executor is None:
        executor = node.executor

    if executor is None:
        raise RuntimeError(
            "No executor provided and node has no executor."
        )

    tasks = [
        executor.create_task(coro)  # type: ignore
        for coro in coroutines
    ]

    results: list[T] = []

    for task in tasks:
        results.append(await task)

    return tuple(results)


def create_one_shot_timer(
    node: Node,
    delay: float,
    callback: Callable[[], Awaitable[Any]],
    callback_group: CallbackGroup | None = None,
) -> Timer:
    """
    Create a timer that invokes an async callback once.
    """
    timer: Timer

    async def wrapped_callback() -> None:
        node.destroy_timer(timer)
        await callback()

    type_forced_cb = cast(
        Callable[..., Any],
        wrapped_callback,
    )

    if callback_group is None:
        callback_group = cb_group

    timer = node.create_timer(
        delay,
        type_forced_cb,
        callback_group,
    )

    return timer


async def wait_future(
    node: Node,
    future: Future[T],
    timeout: float,
    callback_group: CallbackGroup | None = None,
) -> T | None:
    """
    Await a ROS 2 Future with a timeout.

    Returns the future result if it completes before the timeout,
    otherwise returns None.

    The input future is not cancelled.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    result_future: Future[T | None] = Future()

    def _complete(source: Future[T]) -> None:
        if result_future.done():
            return

        exception = source.exception()

        if exception is not None:
            result_future.set_exception(exception)
        else:
            result_future.set_result(source.result())

    def _timeout() -> None:
        if not result_future.done():
            result_future.set_result(None)

    future.add_done_callback(_complete)

    timer = node.create_timer(
        timeout,
        _timeout,
        callback_group=callback_group or cb_group,
    )

    try:
        return await result_future
    finally:
        node.destroy_timer(timer)


class BetterAsyncNode(Node):
    """
    A Node subclass providing convenient async utilities.
    """

    async def asleep(self, seconds: float) -> None:
        await asleep(self, seconds)

    async def agather(
        self,
        *coroutines: Awaitable[T],
        executor: Executor | None = None,
    ) -> tuple[T, ...]:
        return await agather(
            self,
            *coroutines,
            executor=executor,
        )

    def create_one_shot_timer(
        self,
        delay: float,
        callback: Callable[[], Awaitable[Any]],
        callback_group: CallbackGroup | None = None,
    ) -> Timer:
        return create_one_shot_timer(
            self,
            delay,
            callback,
            callback_group,
        )

    async def wait_future(
        self,
        future: Future[T],
        timeout: float,
        callback_group: CallbackGroup | None = None,
    ) -> T | None:
        return await wait_future(
            self,
            future,
            timeout,
            callback_group,
        )