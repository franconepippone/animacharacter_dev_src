from typing import Dict, cast, Tuple
import json
import time
import psutil
import threading

import rclpy
from rclpy.task import Future
from rclpy.node import Node
from std_srvs.srv import Trigger, Trigger_Response

from diagnostic_updater import Updater, DiagnosticStatusWrapper


"""
##!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# DA DEPRECARE!!!!!!!!!!!!!!!!!!

Tutto sto ambaradam può essere riscritto in modo molto più semplice utilizzando rosbridge_server + roslibjs;
questo permette al browser di iscriversi direttametne a topic ros, senza reinventare tutto. I nodi pubblicano status report
e il browser ascotla, FINE. FACILE. Non serve fastapi, ne una gestione manuale delle websocekts, tutto gestito da rosbridge-server.
VEDI CONVERSAZIONE CON CHATGPT, "ROS2 Message Publishing"

INOLTRE per la diagnostica è da utilizzare il framework per diagnostica ufficiale ROS, che pubblica messaggi di diagnostica in modo
strutturato sotto /diagnostics. ES SCRIPT:

import rclpy
from rclpy.node import Node
from diagnostic_updater import Updater, DiagnosticStatusWrapper

class DiagnosticNode(Node):
    def __init__(self):
        super().__init__('diagnostic_node')

        # Diagnostic updater (1 Hz by convention)
        self.updater = Updater(self)
        self.updater.setHardwareID("my_robot")

        # Add a diagnostic task
        self.updater.add("System Status", self.diagnostic_callback)

        # Timer to update diagnostics
        self.timer = self.create_timer(1.0, self.timer_callback)

        # Example state
        self.counter = 0

    def timer_callback(self):
        # Update state
        self.counter += 1

        # Trigger diagnostics update
        self.updater.update()

    def diagnostic_callback(self, stat: DiagnosticStatusWrapper):
        # Fill diagnostic status

        stat.summary(DiagnosticStatusWrapper.OK, "System OK")

        # You can add key-value pairs
        stat.add("counter", self.counter)

        # Example condition
        if self.counter > 10:
            stat.summary(DiagnosticStatusWrapper.WARN, "Counter is high")

        return stat


"""














class StatusMonitorNode(Node):
    def __init__(self):
        super().__init__("status_client_node")
        self.cli = self.create_client(Trigger, "/get_status")
        
        # this stores pids of all monitored processes
        self.pids: set[int] = set()

        self.get_logger().info("Status client node initialized")

    def gather_system_status(self, timeout_sec: float = 2.0) -> dict:
        # registers all the service futures we need under a top-level name
        futures: Dict[str, Future | Dict | list] = {
            'hwmng' : self._get_hardware_manager_status_future(),
            'sys' : self._get_system_resource_status()
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

                # if node sends process pid, we register it so we can monitor the process
                if 'pid' in data:
                    if not data['pid'] in self.pids:
                        if not isinstance(data['pid'], int):
                            self.get_logger().warning("got non integer pid from a status srv response")
                        else:
                            self.get_logger().info("Registered new process PID")
                            self.pids.add(data['pid'])
                        

            except Exception as e:
                self.get_logger().error(f"Error getting future's json: {e}")
                results[key] = None
                
        return results

    def _get_per_process_resource_status(self) -> list:
        data_container = []
        for pid in self.pids:
            if not psutil.pid_exists(pid):
                continue
            proc = psutil.Process(pid)
            data = {}
            data['name'] = proc.name()
            data['cpu'] = proc.cpu_percent()
            data['memory'] = proc.memory_info().rss
            data['uptime'] = int(time.time() - proc.create_time())
            data_container.append(data)
        return data_container

    def _get_system_resource_status(self) -> Dict:
        # Add system stats
        data = {}
        data['cpu'] = psutil.cpu_percent()
        data['memory'] = psutil.virtual_memory().percent
        data['uptime'] = int(time.time() - psutil.boot_time())
        net = psutil.net_io_counters()
        data['bytes_sent'] = net.bytes_sent
        data['bytes_recv'] = net.bytes_recv
        # For rates, simple approximation (would need history for accurate rates)
        data['upload_rate'] = 0  # Placeholder
        data['download_rate'] = 0  # Placeholder

        per_process_data = self._get_per_process_resource_status()

        return {'global': data, 'processes' : per_process_data}
            
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