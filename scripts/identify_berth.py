"""
Phase 1 helper: connect to the Network Rail TD feed for your area and log
every berth step in real time, so you can correlate a train you physically
watch go past with the berth ID(s) involved.

Usage:
    1. Fill in NR_FEED_USERNAME / NR_FEED_PASSWORD / TD_AREA_CODE in .env
       (or export them as environment variables).
    2. Run: python scripts/identify_berth.py
    3. Stand somewhere you can see/hear the train pass, note the wall-clock
       time as precisely as you can.
    4. Ctrl+C to stop, then grep the printed log for events near that
       timestamp. The berth(s) involved in a step at that time are your
       candidates — repeat for a couple more trains to confirm.

Requires: pip install stomp.py python-dotenv
"""

import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import stomp
from dotenv import load_dotenv

load_dotenv()

NR_USER = os.environ["NR_FEED_USERNAME"]
NR_PASS = os.environ["NR_FEED_PASSWORD"]
STOMP_HOST = os.environ.get("NR_STOMP_HOST", "publicdatafeeds.networkrail.co.uk")
STOMP_PORT = int(os.environ.get("NR_STOMP_PORT", "61618"))
TD_AREA_CODE = os.environ["TD_AREA_CODE"]

TOPIC = f"/topic/TD_{TD_AREA_CODE}_SIG_AREA"


def parse_c_class(xml_bytes):
    """
    Pull (from_berth, to_berth, headcode, timestamp) out of a C-class
    (berth step) TD message. Real messages nest this inside a <Sroot>/
    <TD> wrapper; adjust the tag names below if your feed area's schema
    differs slightly (check a few raw messages first if this comes back
    empty).
    """
    root = ET.fromstring(xml_bytes)
    results = []
    for msg in root.iter():
        if msg.tag.endswith("CA_MSG"):  # berth step message
            from_berth = msg.findtext("area_id", "") + msg.findtext("from", "")
            to_berth = msg.findtext("area_id", "") + msg.findtext("to", "")
            headcode = msg.findtext("descr", "")
            ts = msg.findtext("time", "")
            results.append((from_berth, to_berth, headcode, ts))
    return results


class TDListener(stomp.ConnectionListener):
    def on_message(self, frame):
        try:
            events = parse_c_class(frame.body.encode())
        except ET.ParseError:
            print("!! failed to parse message, raw body below:")
            print(frame.body[:500])
            return

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for from_berth, to_berth, headcode, ts in events:
            print(f"{now}  headcode={headcode!r:8} {from_berth} -> {to_berth}")

    def on_error(self, frame):
        print("STOMP error:", frame.body, file=sys.stderr)

    def on_disconnected(self):
        print("Disconnected — reconnecting in 5s...")
        time.sleep(5)
        connect()


conn = None


def connect():
    global conn
    conn = stomp.Connection([(STOMP_HOST, STOMP_PORT)], heartbeats=(15000, 15000))
    conn.set_listener("", TDListener())
    conn.connect(NR_USER, NR_PASS, wait=True)
    conn.subscribe(destination=TOPIC, id=1, ack="auto")
    print(f"Subscribed to {TOPIC}. Watching for berth steps... (Ctrl+C to stop)")


if __name__ == "__main__":
    connect()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping.")
        if conn:
            conn.disconnect()
