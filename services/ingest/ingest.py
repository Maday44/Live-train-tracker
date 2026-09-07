import json
import os
import time
from datetime import datetime, timezone

import stomp
from db import get_db, IS_SQLITE

# Load configuration and credentials from secrets.json
secrets_path = "secrets.json"
if not os.path.exists(secrets_path):
    raise SystemExit(f"Configuration file '{secrets_path}' not found. Please create it.")

with open(secrets_path, "r", encoding="utf-8") as f:
    secrets = json.load(f)

# Allow secrets.json to support both dictionary and list formats
if isinstance(secrets, dict):
    NR_USER = secrets.get("username") or secrets.get("NR_FEED_USERNAME")
    NR_PASS = secrets.get("password") or secrets.get("NR_FEED_PASSWORD")
    STOMP_HOST = secrets.get("host", "publicdatafeeds.networkrail.co.uk")
    STOMP_PORT = int(secrets.get("port", 61618))
    TD_AREA_CODE = secrets.get("area_code", "Q6")
    raw_berths = secrets.get("target_berths", ["Q60684", "Q60685", "Q60686", "Q60687", "Q60688", "Q60689"])
else:
    # Fallback if secrets.json is a list [username, password]
    NR_USER = secrets[0]
    NR_PASS = secrets[1]
    STOMP_HOST = "publicdatafeeds.networkrail.co.uk"
    STOMP_PORT = 61618
    TD_AREA_CODE = "Q6"
    raw_berths = ["Q60684", "Q60685", "Q60686", "Q60687", "Q60688", "Q60689"]

if isinstance(raw_berths, str):
    TARGET_BERTHS = set(b.strip() for b in raw_berths.split(",") if b.strip())
else:
    TARGET_BERTHS = set(str(b).strip() for b in raw_berths)

TOPIC = f"/topic/TD_{TD_AREA_CODE}_SIG_AREA"

if not TARGET_BERTHS:
    raise SystemExit("TARGET_BERTHS is empty. Please define 'target_berths' in secrets.json.")


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
    
    conn = stomp.Connection11(
        [(STOMP_HOST, STOMP_PORT)],
        heartbeats=(15000, 15000)
    )
    conn.set_listener("", TDListener())
    
    conn.connect(
        username=NR_USER,
        password=NR_PASS,
        wait=True,
        headers={"client-id": NR_USER}
    )
    
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