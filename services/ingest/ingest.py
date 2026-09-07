import json
import os
import time
from datetime import datetime, timezone

import stomp
from dotenv import load_dotenv
from db import get_db, IS_SQLITE

load_dotenv()

NR_USER = os.getenv("NR_FEED_USERNAME")
NR_PASS = os.getenv("NR_FEED_PASSWORD")
STOMP_HOST = os.getenv("NR_STOMP_HOST", "publicdatafeeds.networkrail.co.uk")
STOMP_PORT = int(os.getenv("NR_STOMP_PORT", 61618))
TD_AREA_CODE = os.getenv("TD_AREA_CODE", "Q6")
TARGET_BERTHS = set(b.strip() for b in os.environ.get("TARGET_BERTHS", "").split(",") if b.strip())

TOPIC = f"/topic/TD_{TD_AREA_CODE}_SIG_AREA"

if not TARGET_BERTHS:
    raise SystemExit("TARGET_BERTHS is empty. Please set TARGET_BERTHS in .env.")


def insert_raw_event(headcode, berth, direction, event_time):
    conn = get_db()
    try:
        if IS_SQLITE:
            with conn:
                conn.execute(
                    """
                    INSERT INTO raw_events (headcode, berth, direction, event_time, received_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (headcode, berth, direction, event_time, datetime.now(timezone.utc).isoformat()),
                )
        else:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_events (headcode, berth, direction, event_time, received_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (headcode, berth, direction, event_time, datetime.now(timezone.utc)),
                )
    finally:
        conn.close()


def parse_td_messages(body):
    """Network Rail TD feed distributes JSON message payloads."""
    results = []
    try:
        data = json.loads(body)
    except Exception as e:
        print(f"[ingest] JSON decode error: {e}", flush=True)
        return results

    # Data can arrive as a single dict or list of dicts
    if isinstance(data, dict):
        data = [data]

    for wrapper in data:
        for msg_type, msg in wrapper.items():
            if msg_type in ("CA_MSG", "SF_MSG"):
                area = msg.get("area_id", "")
                from_berth = area + msg.get("from", "")
                to_berth = area + msg.get("to", "")
                headcode = msg.get("descr", "")
                ts = msg.get("time", "")
                results.append((from_berth, to_berth, headcode, ts))
    return results


class TDListener(stomp.ConnectionListener):
    def on_message(self, frame):
        events = parse_td_messages(frame.body)
        for from_berth, to_berth, headcode, ts in events:
            if from_berth in TARGET_BERTHS:
                insert_raw_event(headcode, from_berth, "departing", ts)
                print(f"[ingest] {headcode} departing berth {from_berth} at {ts}", flush=True)
            if to_berth in TARGET_BERTHS:
                insert_raw_event(headcode, to_berth, "arriving", ts)
                print(f"[ingest] {headcode} arriving berth {to_berth} at {ts}", flush=True)

    def on_error(self, frame):
        print(f"[ingest] STOMP Error Header: {frame.headers}", flush=True)
        print(f"[ingest] STOMP Error Body: {frame.body}", flush=True)

    def on_disconnected(self):
        print("[ingest] disconnected, reconnecting in 5s...", flush=True)
        time.sleep(5)
        connect()


conn = None

def connect():
    global conn
    print(f"[ingest] Connecting to {STOMP_HOST}:{STOMP_PORT}...", flush=True)
    
    # Initialize standard Connection11 without invalid kwargs
    conn = stomp.Connection11(
        [(STOMP_HOST, STOMP_PORT)],
        heartbeats=(15000, 15000)
    )
    conn.set_listener("", TDListener())
    
    # Pass client-id in headers during connect call
    conn.connect(
        username=NR_USER,
        password=NR_PASS,
        wait=True,
        headers={"client-id": NR_USER}
    )
    
    # Construct Network Rail TD topic string
    topic = f"/topic/TD_{TD_AREA_CODE}_SIG_ALL_DEMO" if "DEMO" in TOPIC else f"/topic/TD_{TD_AREA_CODE}_SIG_ALL"
    
    conn.subscribe(destination=topic, id="1", ack="auto")
    print(f"[ingest] Subscribed to {topic}, watching berths: {TARGET_BERTHS}", flush=True)



if __name__ == "__main__":
    print("[ingest] Service starting...", flush=True)
    connect()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if conn:
            conn.disconnect()