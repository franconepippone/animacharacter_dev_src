import threading
import asyncio
import json
import os
from pathlib import Path
import time
import psutil

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

FRONTEND_DIR = Path(__file__).parent / "frontend"

class StatusClientNode(Node):
    def __init__(self):
        super().__init__("status_client_node")
        self.cli = self.create_client(Trigger, "/get_status")
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Waiting for /get_status service...")
        self.get_logger().info("Connected to /get_status service")

    def get_status(self):
        """Call /get_status service and return dict with system stats."""
        req = Trigger.Request()
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        data = {}
        if future.result() and future.result().success:
            try:
                data = json.loads(future.result().message)
            except json.JSONDecodeError as e:
                self.get_logger().error(f"JSON decode error: {e}")
        else:
            self.get_logger().error("Service call failed")

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

def start_web_server(node: StatusClientNode):
    app = FastAPI()

    # Serve JS
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/get_status_rest")
    async def get_status_rest():
        return node.get_status()

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        while True:
            data = await asyncio.to_thread(node.get_status)
            await ws.send_json(data)
            await asyncio.sleep(1)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

def main():
    rclpy.init()
    node = StatusClientNode()

    web_thread = threading.Thread(target=start_web_server, args=(node,), daemon=True)
    web_thread.start()

    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
