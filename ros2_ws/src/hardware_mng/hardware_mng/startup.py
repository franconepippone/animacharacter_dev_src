"""
Startup script for the Hardware Manager process.
Configures objects, launches background threads, and spins the ros2 node.
"""
import threading as thr
from typing import Callable
from functools import partial
import time
import rclpy
from .hardware_mng_node import HardwareManagerNode
from .dispatcher import Dispatcher
from .looper_util import ThreadedLooper

from mcudrivers.head_driver import HeadMcuDriver, Axys

def main(args=None):

    # instantiate drivers
    driv1 = HeadMcuDriver("COM3")
    driv2 = HeadMcuDriver("COM4") # another driver
    ...

    lock_dr1 = thr.Lock()

    dispatcher = Dispatcher()
    # configure the dispatcher, examples with driv1
    dispatcher.register_handler(1, lambda x: driv1.write(Axys.EYE_L, x))
    dispatcher.register_handler(2, lambda x: driv1.write(Axys.EYE_R, x)) 
    ...

    
    # LOCKS LOGIC IS MISSING0
    looper = ThreadedLooper()
    l1 = looper.add_loop(50, driv1.drive_hardware, lock=lock_dr1)
    l2 = looper.add_loop(50, driv2.drive_hardware)
    ...

    looper.pause_loop(l1.id)
    looper.resume_loop(l2.id)

    looper.start_all()

    ok = looper.all_running()
    print(ok) # from this point on, in the background threads are sending updates to hardware at fixed rate

    # spin ros2 node in this thread 
    rclpy.init(args=args)
    node = HardwareManagerNode(dispatcher)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
