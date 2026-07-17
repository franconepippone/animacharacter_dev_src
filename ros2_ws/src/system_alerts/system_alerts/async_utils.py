from typing import TypeVar

from rclpy.task import Future
from rclpy.node import Node
from rclpy.callback_groups import CallbackGroup

T = TypeVar("T")


async def wait_for(
    node: Node,
    future: Future[T],
    timeout: float,
    callback_group: CallbackGroup | None = None,
) -> T | None:
    """
    Await a ROS 2 Future with a timeout.

    Returns the future result if it completes before the timeout, otherwise
    returns None. The input future is not modified or cancelled.
    """

    if timeout <= 0:
        raise ValueError("timeout must be positive")

    result_future: Future[T | None] = Future()

    def _complete(source: Future[T]) -> None:
        if not result_future.done():
            result_future.set_result(source.result())

    future.add_done_callback(_complete)

    def _timeout() -> None:
        if not result_future.done():
            result_future.set_result(None)

    timer = node.create_timer(
        timeout,
        _timeout,
        callback_group=callback_group,
    )

    try:
        return await result_future
    finally:
        node.destroy_timer(timer)