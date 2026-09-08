import json
import asyncio
from typing import Set
from datetime import datetime, timezone as dt_timezone
from pytz import timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
import stomp

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
TARGET_BERTHS = ["0684", "0685", "0686", "0687"]

class StompListener(stomp.ConnectionListener):
    def __init__(self, loop):
        self.loop = loop

    def on_connected(self, frame):
        print(f"✓ Connected to Network Rail! Tracking Areas {TARGET_AREAS}, Berths {TARGET_BERTHS}...")

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

                            print(f"🚆 LIVE TRAIN MATCH: {headcode} [{area_id}] {from_berth} ---> {to_berth}")

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

    HOST = "publicdatafeeds.networkrail.co.uk"
    PORT = 61618

    conn = stomp.Connection12([(HOST, PORT)], keepalive=True, heartbeats=(5000, 5000))
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


# Web Dashboard Page
@app.get("/")
async def get_dashboard():
    return HTMLResponse(content=HTML_CONTENT)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Train Monitor</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; display: flex; justify-content: center; }
        .container { max-width: 800px; width: 100%; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
        .status-badge { background: #10b981; color: #022c22; padding: 6px 12px; border-radius: 9999px; font-weight: bold; font-size: 14px; }
        .alert-box { display: none; background: #ef4444; color: #fff; padding: 24px; border-radius: 12px; text-align: center; font-size: 28px; font-weight: bold; margin-bottom: 24px; }
        .card { background: #1e293b; border-radius: 12px; padding: 20px; }
        .log-list { list-style: none; padding: 0; margin: 0; }
        .log-item { padding: 12px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; }
        button { background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-right: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Train Monitor</h1>
            <div>
                <span id="connection-status" class="status-badge">Connecting...</span>
            </div>
        </div>
        <div id="alert-box" class="alert-box">
            TRAIN PASSING!
            <div id="alert-details" style="font-size: 18px; margin-top: 8px; font-weight: normal;"></div>
        </div>
        <div class="card">
            <h2>Recent Train Activity</h2>
            <ul id="log-list" class="log-list">
                <li style="color: #94a3b8; text-align: center; padding: 12px;">Waiting for train activity...</li>
            </ul>
        </div>
    </div>
    <script>
        const evtSource = new EventSource("/events");
        const statusBadge = document.getElementById("connection-status");
        const alertBox = document.getElementById("alert-box");
        const alertDetails = document.getElementById("alert-details");
        const logList = document.getElementById("log-list");
        let firstLog = true;

        async function triggerTest() {
            await fetch('/test-alert', { method: 'POST' });
        }

        evtSource.onopen = () => { statusBadge.textContent = "LIVE"; statusBadge.style.background = "#10b981"; };
        evtSource.onerror = () => { statusBadge.textContent = "OFFLINE"; statusBadge.style.background = "#f59e0b"; };

        evtSource.addEventListener("train_alert", (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "ALERT") {
                alertBox.style.display = "block";
                alertDetails.textContent = `${data.train_id} (${data.area}) moved ${data.from_berth} ➔ ${data.to_berth} at ${data.time}`;
                
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    osc.connect(ctx.destination);
                    osc.frequency.value = 880;
                    osc.start();
                    osc.stop(ctx.currentTime + 0.5);
                } catch (e) {}

                setTimeout(() => { alertBox.style.display = "none"; }, 10000);

                if (firstLog) { logList.innerHTML = ""; firstLog = false; }
                const li = document.createElement("li");
                li.className = "log-item";
                li.innerHTML = `<span><strong>${data.train_id}</strong> [${data.area}] (${data.from_berth} ➔ ${data.to_berth})</span> <span>${data.time}</span>`;
                logList.insertBefore(li, logList.firstChild);
            }
        });
    </script>
</body>
</html>
"""