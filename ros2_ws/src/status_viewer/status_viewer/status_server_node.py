import threading
import asyncio
import json
import psutil
from pathlib import Path
import time
import os

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger, Trigger_Request, Trigger_Response

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

with open(Path(__file__).parent / 'frontend' / 'index.html', 'r') as f:
    HTML = f.read()

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
import time
import psutil
import json

class StatusNode(Node):

    def __init__(self):
        super().__init__("status_viewer_node")

        self.start_time = time.time()

        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.time()

        self.latest_data = {}
        self.create_timer(1.0, self.update_status)

        # --- Create service ---
        self.srv = self.create_service(
            Trigger,
            '/get_status',
            self.get_status_callback
        )

        self.get_logger().info("StatusNode service /get_status ready")

    def update_status(self):
        now = time.time()
        current_net = psutil.net_io_counters()
        elapsed = now - self.prev_time

        upload_rate = (current_net.bytes_sent - self.prev_net.bytes_sent) / elapsed / 1024
        download_rate = (current_net.bytes_recv - self.prev_net.bytes_recv) / elapsed / 1024

        self.prev_net = current_net
        self.prev_time = now

        self.latest_data = {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "uptime": int(now - self.start_time),
            "bytes_sent": current_net.bytes_sent,
            "bytes_recv": current_net.bytes_recv,
            "upload_rate": round(upload_rate, 1),
            "download_rate": round(download_rate, 1),
        }

    # --- New service callback ---
    def get_status_callback(self, request: Trigger_Request, response: Trigger_Response):
        """
        Responds to /get_status Trigger service calls.
        Puts the latest hardware metrics into JSON in the 'message' field.
        """
        try:
            # Convert the latest_data dict to JSON string
            response.message = json.dumps(self.latest_data)
            response.success = True
        except (TypeError, OverflowError) as e:
            response.message = f"Failed to serialize data: {e}"
            response.success = False

        return response


def start_web_server(node: StatusNode):

    app = FastAPI()

    base_dir = os.path.dirname(__file__)
    frontend_dir = os.path.join(base_dir, "frontend")

    # Serve JS files under /static
    app.mount(
        "/static",
        StaticFiles(directory=frontend_dir),
        name="static",
    )

    @app.get("/get_status_rest")
    async def get_status_rest():
        # Get latest hardware metrics
        hw_data = node.latest_data

        # Get looper JSON (if you have ThreadedLooper instance)
        loops_json = looper.status_as_json()  # assuming `looper` is global/shared

        return {
            **hw_data,
            "loops_json": loops_json
        }


    @app.get("/")
    async def index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        while True:
            await ws.send_json(node.latest_data)
            await asyncio.sleep(1)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

def main():
    rclpy.init()
    node = StatusNode()

    # Run web server in separate thread
    web_thread = threading.Thread(target=start_web_server, args=(node,), daemon=True)
    web_thread.start()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
