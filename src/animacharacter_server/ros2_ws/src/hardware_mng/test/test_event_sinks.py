from threading import Event, Thread
import time

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from lifecycle_pkg.events import LifecycleEvent

from hardware_mng.event_sinks import ControllerEventSink, ExecutorEventQueue


def test_controller_event_sink_wakes_an_executor_coroutine():
    context = Context()
    rclpy.init(args=[], context=context)
    node = Node("event_sink_test", context=context)
    executor = SingleThreadedExecutor(context=context)
    executor.add_node(node)
    queue: ExecutorEventQueue[tuple[str, LifecycleEvent]] = ExecutorEventQueue()
    queue.attach_executor(executor)
    sink = ControllerEventSink("controller-a", queue)
    event = LifecycleEvent(message="controller started")
    received = Event()
    result: list[tuple[str, LifecycleEvent]] = []

    async def consume_one_event():
        result.append(await queue.get())
        received.set()

    try:
        executor.create_task(consume_one_event())
        executor.spin_once(timeout_sec=0.1)

        producer = Thread(target=sink.emit, args=(event,))
        producer.start()
        producer.join(timeout=1.0)
        assert not producer.is_alive()

        deadline = time.monotonic() + 1.0
        while not received.is_set() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)

        assert received.is_set()
        assert result == [("controller-a", event)]
    finally:
        executor.remove_node(node)
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown(context=context)
