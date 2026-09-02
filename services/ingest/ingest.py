"""
Ingest service: maintains a persistent STOMP connection to the Network
Rail TD feed, filters berth-step events down to TARGET_BERTHS, and writes
matches to the `raw_events` table for the enrichment service to pick up.

This is scripts/identify_berth.py's logic, minus the "log everything"
behaviour and plus a DB write — split out once you know your berth IDs.
"""

import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import stomp
import psycopg2
from dotenv import load_dotenv

load_dotenv()

NR_USER = os.environ["NR_FEED_USERNAME"]
NR_PASS = os.environ["NR_FEED_PASSWORD"]
STOMP_HOST = os.environ.get("NR_STOMP_HOST", "publicdatafeeds.networkrail.co.uk")
STOMP_PORT = int(os.environ.get("NR_STOMP_PORT", "61618"))
TD_AREA_CODE = os.environ["TD_AREA_CODE"]
TARGET_BERTHS = set(b.strip() for b in os.environ.get("TARGET_BERTHS", "").split(",") if b.strip())
DATABASE_URL = os.environ["DATABASE_URL"]

TOPIC = f"/topic/TD_{TD_AREA_CODE}_SIG_AREA"

if not TARGET_BERTHS:
    raise SystemExit(
        "TARGET_BERTHS is empty. Run scripts/identify_berth.py first to "
        "find your berth ID(s), then set TARGET_BERTHS in .env."
    )


def get_db():
    return psycopg2.connect(DATABASE_URL)


def insert_raw_event(headcode, berth, direction, event_time):
    conn = get_db()
    try:
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


def parse_c_class(xml_bytes):
    root = ET.fromstring(xml_bytes)
    results = []
    for msg in root.iter():
        if msg.tag.endswith("CA_MSG"):
            area = msg.findtext("area_id", "")
            from_berth = area + msg.findtext("from", "")
            to_berth = area + msg.findtext("to", "")
            headcode = msg.findtext("descr", "")
            ts = msg.findtext("time", "")
            results.append((from_berth, to_berth, headcode, ts))
    return results


class TDListener(stomp.ConnectionListener):
    def on_message(self, frame):
        try:
            events = parse_c_class(frame.body.encode())
        except ET.ParseError:
            return

        for from_berth, to_berth, headcode, ts in events:
            if from_berth in TARGET_BERTHS:
                insert_raw_event(headcode, from_berth, "departing", ts)
                print(f"[ingest] {headcode} departing berth {from_berth} at {ts}")
            if to_berth in TARGET_BERTHS:
                insert_raw_event(headcode, to_berth, "arriving", ts)
                print(f"[ingest] {headcode} arriving berth {to_berth} at {ts}")

    def on_error(self, frame):
        print("[ingest] STOMP error:", frame.body)

    def on_disconnected(self):
        print("[ingest] disconnected, reconnecting in 5s...")
        time.sleep(5)
        connect()


conn = None


def connect():
    global conn
    conn = stomp.Connection([(STOMP_HOST, STOMP_PORT)], heartbeats=(15000, 15000))
    conn.set_listener("", TDListener())
    conn.connect(NR_USER, NR_PASS, wait=True)
    conn.subscribe(destination=TOPIC, id=1, ack="auto")
    print(f"[ingest] subscribed to {TOPIC}, watching berths: {TARGET_BERTHS}")


if __name__ == "__main__":
    connect()
    while True:
        time.sleep(1)
