from typing import Dict, cast, Tuple
import json
import time
import psutil
import threading

import rclpy
from rclpy.task import Future
from rclpy.node import Node
from std_srvs.srv import Trigger, Trigger_Response

class StatusMonitorNode(Node):
    def __init__(self):
        super().__init__("status_client_node")
        self.cli = self.create_client(Trigger, "/get_status")
        self.get_logger().info("Status client node initialized")

    def gather_system_status(self, timeout_sec: float = 2.0) -> dict:
        # registers all the service futures we need under a top-level name
        futures: Dict[str, Future | Dict] = {
            'hwmng' : self._get_hardware_manager_status_future(),
            'sys_resources' : self._get_system_resource_status()
        }

        start_time = time.time()

        while any(not f.done() for f in futures.values() if isinstance(f, Future)):
            rclpy.spin_once(self, timeout_sec=0.1)

            if (time.time() - start_time) > timeout_sec:
                self.get_logger().warn("Timeout reached before all services responded")
                break
        
        # construct dict result from futures
        results = {}
        for key, fut in futures.items():
            if not isinstance(fut, Future):
                # we handle special case where data is already a dict first
                results[key] = fut
                continue
        
            if not fut.done():
                fut.cancel()
                continue

            try:
                result: Trigger_Response = cast(Trigger_Response, fut.result())
                data = json.loads(result.message)
                results[key] = data
            except Exception as e:
                self.get_logger().error(f"Error getting future's json: {e}")
                results[key] = None
                
        return results

    def _get_system_resource_status(self) -> Dict:
        data = {}
        # Add system stats
        data['cpu'] = psutil.cpu_percent()
        data['memory'] = psutil.virtual_memory().percent
        data['uptime'] = int(time.time() - psutil.boot_time())
        net = psutil.net_io_counters()
        data['bytes_sent'] = net.bytes_sent
        data['bytes_recv'] = net.bytes_recv
        # For rates, simple approximation (would need history for accurate rates)
        data['upload_rate'] = 0  # Placeholder
        data['download_rate'] = 0  # Placeholder
        return data
            
    def _get_hardware_manager_status_future(self) -> Future:
        """Call /get_status service and return a future of the result"""
        req = Trigger.Request()
        return self.cli.call_async(req) 

def spin_node_threaded() -> Tuple[threading.Thread, StatusMonitorNode]:
    rclpy.init()
    node = StatusMonitorNode()
    
    def spin():
        rclpy.spin(node)
        node.destroy_node()
        rclpy.shutdown()

    t = threading.Thread(target=spin, daemon=True, name='status monitor node executor thread')
    t.start()

    return t, node