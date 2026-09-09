import json
import asyncio
from typing import Set
from datetime import datetime, timezone as dt_timezone
from flask import render_template
from pytz import timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse
import stomp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

TIMEZONE_LONDON = timezone("Europe/London")

# Store active SSE queues and WebSocket connections
connected_sse_clients: Set[asyncio.Queue] = set()
connected_websockets: Set[WebSocket] = set()

# Load secrets
with open("secrets.json") as f:
    SECRETS = json.load(f)

# Targets matching your housetrack.py config
TARGET_AREAS = ["Q6"]
TARGET_BERTHS = ["0684", "0685"]
# TARGET_BERTHS = ["0684", "0685", "0686", "0687"]


class StompListener(stomp.ConnectionListener):
    def __init__(self, loop):
        self.loop = loop

    def on_connected(self, frame):
        print(f" Connected to Network Rail! Tracking Areas {TARGET_AREAS}, Berths {TARGET_BERTHS}...")

    def on_message(self, frame):
        try:
            parsed_body = json.loads(frame.body)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                msg_type = msg.get("msg_type")

                # CA = Berth Step, CB = Cancel, CC = Interpose
                if msg_type in ["CA", "CB", "CC"]:
                    area_id = msg.get("area_id", "")
                    from_berth = msg.get("from", "")
                    to_berth = msg.get("to", "")
                    headcode = msg.get("descr", "TRAIN")

                    # Check if movement matches target area & berth
                    if area_id in TARGET_AREAS:
                        if from_berth in TARGET_BERTHS or to_berth in TARGET_BERTHS:
                            ts = int(msg.get("time", 0)) / 1000
                            utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)
                            uk_dt = utc_dt.astimezone(TIMEZONE_LONDON)
                            time_str = uk_dt.strftime("%H:%M:%S")

                            active_berth = to_berth if to_berth in TARGET_BERTHS else from_berth

                            alert_payload = {
                                "type": "ALERT",
                                "train_id": headcode,
                                "berth": active_berth,
                                "area": area_id,
                                "from_berth": from_berth,
                                "to_berth": to_berth,
                                "time": time_str,
                                "message": f"Train {headcode} at berth {active_berth}!"
                            }

                            print(f"LIVE TRAIN MATCH: {headcode} [{area_id}] {from_berth} ---> {to_berth} at {time_str}")

                            # Broadcast to SSE clients
                            for queue in list(connected_sse_clients):
                                self.loop.call_soon_threadsafe(queue.put_nowait, alert_payload)

                            # Broadcast to WebSocket clients
                            for ws in list(connected_websockets):
                                self.loop.create_task(ws.send_text(json.dumps(alert_payload)))
        except Exception as e:
            print(f"Parsing error: {e}")

def start_stomp_listener(loop):
    feed_username = SECRETS["username"] if isinstance(SECRETS, dict) else SECRETS[0]
    feed_password = SECRETS["password"] if isinstance(SECRETS, dict) else SECRETS[1]

    host = SECRETS["host"]
    port = SECRETS["port"]

    conn = stomp.Connection12([(host, port)], keepalive=True, heartbeats=(5000, 5000))
    conn.set_listener('train_listener', StompListener(loop))
    conn.connect(username=feed_username, passcode=feed_password, wait=True)
    conn.subscribe(destination="/topic/TD_ALL_SIG_AREA", id=1, ack='auto')

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, start_stomp_listener, loop)


@app.get("/events")
async def sse_endpoint():
    queue = asyncio.Queue()
    connected_sse_clients.add(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield {"event": "train_alert", "data": json.dumps(data)}
        except (asyncio.CancelledError, Exception):
            pass
        finally:
            connected_sse_clients.discard(queue)

    return EventSourceResponse(event_generator())

# WebSocket Endpoint
@app.websocket("/events/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)


@app.get("/")
async def get_dashboard():
    return FileResponse("templates/live_train_tracker_home.html")