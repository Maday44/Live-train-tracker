"""
API service: REST endpoint for recent events, WebSocket for live pushes.

This is the single backend consumed by both the web dashboard (Phase 4)
and the physical display (Phase 5) — neither client talks to the DB or
the TD feed directly, they only talk to this service.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import init_db, fetch_recent_events, get_db

app = FastAPI(title="trainwatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before exposing outside your network
    allow_methods=["*"],
    allow_headers=["*"],
)

active_websockets: list[WebSocket] = []


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/events/recent")
def get_recent_events(limit: int = 50):
    return fetch_recent_events(limit=limit)


@app.websocket("/events/live")
async def events_live(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # Keep the connection open; this endpoint is push-only from the
            # server side, so we just wait for the client to disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


async def broadcast_event(event: dict):
    dead = []
    for ws in active_websockets:
        try:
            await ws.send_text(json.dumps(event, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_websockets.remove(ws)


async def poll_for_new_events():
    """
    Simple polling bridge from Postgres to connected WebSocket clients.
    Fine for a single-home project; swap for LISTEN/NOTIFY if you want to
    avoid the poll interval later.
    """
    last_seen_id = 0
    while True:
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, headcode, berth, direction, destination, "
                    "delay_minutes, created_at FROM passing_events "
                    "WHERE id > %s ORDER BY id ASC",
                    (last_seen_id,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        for row in rows:
            last_seen_id = row[0]
            await broadcast_event(
                {
                    "id": row[0],
                    "headcode": row[1],
                    "berth": row[2],
                    "direction": row[3],
                    "destination": row[4],
                    "delay_minutes": row[5],
                    "created_at": row[6],
                }
            )
        await asyncio.sleep(3)


@app.on_event("startup")
async def start_poller():
    asyncio.create_task(poll_for_new_events())


# Serve the static dashboard from /web at the site root, e.g. http://localhost:8000/
app.mount("/", StaticFiles(directory="/web", html=True), name="web")
