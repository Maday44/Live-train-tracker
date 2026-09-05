import json
import logging
import sys
import time
from datetime import datetime
import stomp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

try:
    with open("secrets.json") as f:
        NR_USER, NR_PASS = json.load(f)
except FileNotFoundError:
    print("FAIL: secrets.json file not found.")
    sys.exit(1)

STOMP_HOST = "publicdatafeeds.networkrail.co.uk"
STOMP_PORT = 61618
TOPIC = "/topic/TD_ALL_SIG_AREA"
TEST_DURATION_SECONDS = 30

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
            preview = frame.body[:120].replace("\n", " ")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Message #{message_count} received: {preview}...")

    def on_error(self, frame):
        error_messages.append(frame.body)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STOMP ERROR frame: {frame.body!r}")

print(f"Connecting to {STOMP_HOST}:{STOMP_PORT} (SSL) ...")
print(f"Subscribing to topic: {TOPIC}\n")

conn = stomp.Connection12([(STOMP_HOST, STOMP_PORT)], keepalive=True, heartbeats=(5000, 5000))
conn.set_ssl(for_hosts=[(STOMP_HOST, STOMP_PORT)])
conn.set_listener("", TestListener())

try:
    conn.connect(username=NR_USER, passcode=NR_PASS, wait=True)
except Exception as e:
    print(f"\nFAIL: Could not connect/authenticate: {e}")
    sys.exit(1)

conn.subscribe(destination=TOPIC, id=1, ack="auto")

start = time.time()
while time.time() - start < TEST_DURATION_SECONDS:
    time.sleep(1)

conn.disconnect()

print("\n" + "=" * 50)
print(f"Connected:         {'YES' if connected else 'NO'}")
print(f"Messages received: {message_count}")
print(f"Error frames:      {len(error_messages)}")