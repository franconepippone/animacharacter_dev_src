import time

from looper import LoopAction, LoopRequest, LoopSupervisor, Signal


def test_loop_signal_handler_is_called_for_stop_requests():
    seen = []

    def job(_input_queue, _output_queue):
        return LoopRequest(
            action=LoopAction.STOP,
            signal=Signal("shutdown"),
        )

    def on_signal(signal):
        seen.append(signal)

    looper = LoopSupervisor()
    loop = looper.add_loop("test", 100.0, job, start_now=True, signal_handler=on_signal)

    if loop._thread is not None:
        loop._thread.join(timeout=0.5)

    time.sleep(0.05)
    assert [signal.name for signal in seen] == ["shutdown"]
