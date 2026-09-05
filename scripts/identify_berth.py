#!/usr/bin/env python3

import json
import sys
from datetime import datetime
from time import sleep

import stomp
from pytz import timezone

TIMEZONE_LONDON = timezone("Europe/London")

# Message Types
C_BERTH_STEP = "CA"
C_BERTH_CANCEL = "CB"
C_BERTH_INTERPOSE = "CC"

TOPIC = "/topic/TD_ALL_SIG_AREA"


def process_td_message(parsed_body):
    """Parses JSON array directly from Network Rail TD feed."""
    for outer_message in parsed_body:
        message = list(outer_message.values())[0]
        message_type = message.get("msg_type")

        if message_type in [C_BERTH_STEP, C_BERTH_CANCEL, C_BERTH_INTERPOSE]:
            area_id = message.get("area_id", "")
            timestamp = int(message.get("time", 0)) / 1000
            description = message.get("descr", "")
            from_berth = message.get("from", "")
            to_berth = message.get("to", "")

            utc_datetime = datetime.utcfromtimestamp(timestamp)
            uk_datetime = TIMEZONE_LONDON.fromutc(utc_datetime)

            print(
                "{} [{:2}] {:2} {:4} {:>5}->{:5}".format(
                    uk_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    message_type,
                    area_id,
                    description,
                    from_berth,
                    to_berth,
                )
            )


class VerboseListener(stomp.ConnectionListener):
    def on_connecting(self, host_and_port):
        print(f"-> Attempting STOMP handshake with {host_and_port}...")

    def on_connected(self, frame):
        print("-> STOMP Handshake Successful! Connected to broker.")

    def on_message(self, frame):
        try:
            parsed_body = json.loads(frame.body)
            process_td_message(parsed_body)
        except Exception as e:
            print(f"Error parsing frame: {e}", file=sys.stderr)

    def on_error(self, frame):
        print("\n=== STOMP ERROR RECEIVED FROM BROKER ===")
        print(f"Headers: {frame.headers}")
        print(f"Body: {frame.body}")
        print("=======================================\n")

    def on_disconnected(self):
        print("-> Connection dropped by broker.")


if __name__ == "__main__":
    try:
        with open("secrets.json") as f:
            secrets = json.load(f)
            if isinstance(secrets, dict):
                feed_username = secrets["username"]
                feed_password = secrets["password"]
            else:
                feed_username, feed_password = secrets[0], secrets[1]
    except (FileNotFoundError, KeyError, IndexError):
        print("Error reading secrets.json")
        sys.exit(1)

    HOST = "publicdatafeeds.networkrail.co.uk"
    PORT = 61613

    print(f"Connecting to Network Rail TD Feed ({HOST}:{PORT})...")

    # Disable auto-reconnect loops on connection drop so we see the exact response
    connection = stomp.Connection12(
        [(HOST, PORT)],
        keepalive=True,
        heartbeats=(5000, 5000)
    )
    connection.set_listener("verbose", VerboseListener())

    # Mandatory headers required by Network Rail ActiveMQ
    connect_headers = {
        "username": feed_username,
        "passcode": feed_password,
        "wait": True,
        "client-id": feed_username,
        "host": HOST,
    }

    try:
        connection.connect(**connect_headers)
    except Exception as e:
        print(f"\nConnect failed: {type(e).__name__} - {e}")
        sys.exit(1)

    print(f"Subscribing to topic: {TOPIC}")
    connection.subscribe(destination=TOPIC, id=1, ack="auto")
    print("Listening for live berth steps... (Press Ctrl+C to stop)\n")

    try:
        while connection.is_connected():
            sleep(1)
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        connection.disconnect()