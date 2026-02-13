import asyncio
from rclpy.logging import RcutilsLogger
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

from status_monitor_node import StatusMonitorNode, spin_node_threaded

logger = RcutilsLogger('stats web dashboard - main.py')

app = FastAPI()
templates = Jinja2Templates(directory="templates")


app.mount("/static", StaticFiles(directory="static"), name="static")

clients: set[WebSocket] = set()
broadcast_task: asyncio.Task | None = None
statnode: StatusMonitorNode | None = None

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global broadcast_task

    await websocket.accept()
    clients.add(websocket)

    logger.info(f"Client connected. Total: {len(clients)}")

    # Start broadcaster if this is the first client
    if len(clients) == 1:
        logger.info("Starting broadcaster...")
        broadcast_task = asyncio.create_task(broadcaster())

    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        clients.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(clients)}")

        # Stop broadcaster if no clients left
        if len(clients) == 0 and broadcast_task:
            logger.info("Stopping broadcaster...")
            broadcast_task.cancel()
            broadcast_task = None


async def broadcaster():
    logger.info("Broadcaster running confirmed")
    try:
        while True:
            data = {}
            if statnode:
                data = statnode.gather_system_status()
            
            """
            data = {
                "cpu": random.randint(0, 100),
                "memory": random.randint(0, 100),
                "tasks": random.randint(10, 50),
                "errors": random.randint(0, 10),
                "throughput": random.randint(50, 150)
            }"""

            # Send only if clients exist (extra safety)
            if clients:
                await asyncio.gather(
                    *(client.send_json(data) for client in clients),
                    return_exceptions=True
                )

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Broadcaster stopped cleanly.")
    except Exception as e:
        logger.error(f"Broadcaster task crashed unexpectedly: {e}")


def main():
    global statnode
    _thread, statnode = spin_node_threaded()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()