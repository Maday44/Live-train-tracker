"""
Standalone connection test — checks ONLY that:
  1. Your Network Rail credentials authenticate successfully
  2. The STOMP connection stays open
  3. Your TD_AREA_CODE topic is valid and delivering messages

Does NOT attempt to parse berth data — this isolates "is the connection
even working" from "is my parsing logic right," so you know which one
to debug if something's wrong.

Usage:
    python scripts/test_connection.py

It will print a clear PASS/FAIL summary after 30 seconds and exit ---
no need to Ctrl+C.
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime, timezone

import stomp
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
load_dotenv()


NR_USER = os.environ.get("NR_FEED_USERNAME")
NR_PASS = os.environ.get("NR_FEED_PASSWORD")
STOMP_HOST = os.environ.get("NR_STOMP_HOST", "publicdatafeeds.networkrail.co.uk")
STOMP_PORT = int(os.environ.get("NR_STOMP_PORT", "61618"))
TD_AREA_CODE = os.environ.get("TD_AREA_CODE")

TEST_DURATION_SECONDS = 30

if not NR_USER or not NR_PASS:
    print("FAIL: NR_FEED_USERNAME or NR_FEED_PASSWORD not set in .env")
    sys.exit(1)

if not TD_AREA_CODE:
    print("FAIL: TD_AREA_CODE not set in .env")
    sys.exit(1)

TOPIC = f"/topic/TD_{TD_AREA_CODE}_SIG_AREA"

message_count = 0
connected = False
error_messages = []


class TestListener(stomp.ConnectionListener):
    def on_connected(self, frame):
        global connected
        connected = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected + authenticated OK")

    def on_message(self, frame):
        global message_count
        message_count += 1
        if message_count <= 3:
            preview = frame.body[:150].replace("\n", " ")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Message #{message_count} received: {preview}...")

    def on_error(self, frame):
        error_messages.append(frame.body)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STOMP ERROR frame: {frame.body!r}")

    def on_disconnected(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Disconnected")


print(f"Connecting to {STOMP_HOST}:{STOMP_PORT} (SSL) ...")
print(f"Subscribing to topic: {TOPIC}")
print(f"Will listen for {TEST_DURATION_SECONDS}s then report results.\n")

conn = stomp.Connection([(STOMP_HOST, STOMP_PORT)], heartbeats=(15000, 15000))
conn.set_ssl(for_hosts=[(STOMP_HOST, STOMP_PORT)])
conn.set_listener("", TestListener())

connect_error = []


def do_connect():
    try:
        conn.connect(NR_USER, NR_PASS, wait=True)
    except Exception as e:
        connect_error.append(e)


connect_thread = threading.Thread(target=do_connect, daemon=True)
connect_thread.start()
connect_thread.join(timeout=15)

if connect_thread.is_alive():
    print(
        "\nFAIL: connect() did not respond within 15 seconds.\n"
        "This usually means a firewall (Windows Defender, antivirus, or "
        "network/router) is blocking outbound connections on port "
        f"{STOMP_PORT}, or the host is unreachable. It is NOT a "
        "credentials problem if you see this — a bad password fails fast, "
        "it doesn't hang."
    )
    sys.exit(1)

if connect_error:
    print(f"\nFAIL: could not connect/authenticate: {connect_error[0]}")
    sys.exit(1)

if not connected:
    print("\nFAIL: connect() returned but no CONNECTED frame was confirmed.")
    sys.exit(1)

conn.subscribe(destination=TOPIC, id=1, ack="auto")

start = time.time()
while time.time() - start < TEST_DURATION_SECONDS:
    time.sleep(1)

conn.disconnect()

print("\n" + "=" * 50)
print("RESULT")
print("=" * 50)
print(f"Connected:        {'YES' if connected else 'NO'}")
print(f"Messages received: {message_count}")
print(f"Error frames:      {len(error_messages)}")

if connected and message_count > 0 and not error_messages:
    print("\nPASS — connection and topic are both working.")
elif connected and message_count == 0:
    print(
        "\nPARTIAL — auth worked and connection stayed open, but zero "
        "messages arrived. Likely cause: TD_AREA_CODE is wrong, or "
        "genuinely no trains moved in this area during the test window "
        "(unlikely for 30s in a busy area — check the code first)."
    )
elif not connected:
    print(
        "\nFAIL — could not establish/confirm connection. Check "
        "NR_FEED_USERNAME/PASSWORD are correct and your account is "
        "approved for TD feed access on datafeeds.networkrail.co.uk."
    )
if error_messages:
    print(
        "\nSTOMP ERROR frames were received during the test — this "
        "usually means either bad credentials, an invalid topic name, "
        "or an existing active connection using the same account "
        "(Network Rail feeds typically only allow one connection per "
        "account at a time)."
    )