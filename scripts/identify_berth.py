#!/usr/bin/env python3

import json
import sys
from datetime import datetime
from time import sleep

import stomp
from pytz import timezone

TIMEZONE_LONDON = timezone("Europe/London")
TOPIC = "/topic/TD_ALL_SIG_AREA"

class Listener(stomp.ConnectionListener):
    def on_connected(self, frame):
        print("✓ Connected successfully!")

    def on_message(self, frame):
        try:
            parsed_body = json.loads(frame.body)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                if msg.get("msg_type") in ["CA", "CB", "CC"]:
                    ts = int(msg.get("time", 0)) / 1000
                    uk_dt = TIMEZONE_LONDON.fromutc(datetime.utcfromtimestamp(ts))
                    print(
                        f"{uk_dt.strftime('%H:%M:%S')} [{msg.get('msg_type')}] "
                        f"Area: {msg.get('area_id')} Descr: {msg.get('descr')} "
                        f"{msg.get('from')} -> {msg.get('to')}"
                    )
        except Exception as e:
            print(f"Parsing error: {e}", file=sys.stderr)

    def on_error(self, frame):
        print(f"\n=== STOMP ERROR ===\n{frame.body}\n")

    def on_disconnected(self):
        print("Disconnected from stream.")

if __name__ == "__main__":
    try:
        with open("secrets.json") as f:
            secrets = json.load(f)
            user = secrets["username"] if isinstance(secrets, dict) else secrets[0]
            pwd = secrets["password"] if isinstance(secrets, dict) else secrets[1]
    except Exception as e:
        print(f"Error reading secrets.json: {e}")
        sys.exit(1)

    HOST = "127.0.0.1"
    PORT = 61618
    REMOTE_HOST = "publicdatafeeds.networkrail.co.uk"

    print(f"Connecting to local bridge ({HOST}:{PORT})...")

    conn = stomp.Connection12([(HOST, PORT)], keepalive=True, heartbeats=(5000, 5000))
    conn.set_listener("", Listener())

    try:
        conn.connect(
            username=user,
            passcode=pwd,
            wait=True,
            headers={"client-id": user, "host": REMOTE_HOST}
        )
        print("Authenticated successfully.")
    except Exception as e:
        print(f"Connection failure: {e}")
        sys.exit(1)

    print(f"Subscribing to topic: {TOPIC}")
    conn.subscribe(destination=TOPIC, id=1, ack="auto")
    print("Listening for live berth steps... (Press Ctrl+C to stop)\n")

    try:
        while conn.is_connected():
            sleep(1)
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        conn.disconnect()