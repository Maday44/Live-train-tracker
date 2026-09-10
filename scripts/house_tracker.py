#!/usr/bin/env python3

# Standard
import argparse
import json
import sys
from datetime import datetime
from datetime import timezone as dt_timezone
from time import sleep

# Third party
import stomp
from pytz import timezone

TIMEZONE_LONDON = timezone("Europe/London")


TARGET_AREAS = ["Q6", "MP"]
TARGET_BERTHS = ["0684", "0685"]


class Listener(stomp.ConnectionListener):
    _mq: stomp.Connection

    def __init__(self, mq: stomp.Connection, durable=False):
        self._mq = mq
        self.is_durable = durable

    def on_connected(self, frame):
        print(
            f"✓ Connected! Tracking   (Areas {TARGET_AREAS}, Berths {TARGET_BERTHS})...\n"
        )

    def on_message(self, frame):
        headers, message_raw = frame.headers, frame.body

        if self.is_durable:
            self._mq.ack(id=headers["message-id"], subscription=headers["subscription"])

        try:
            parsed_body = json.loads(message_raw)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                msg_type = msg.get("msg_type")

                # CA = Berth Step, CB = Cancel, CC = Interpose
                if msg_type in ["CA", "CB", "CC"]:
                    area_id = msg.get("area_id", "")
                    from_berth = msg.get("from", "")
                    to_berth = msg.get("to", "")
                    headcode = msg.get("descr", "")

                    # Check if movement matches our target areas & berths
                    if area_id in TARGET_AREAS:
                        if from_berth in TARGET_BERTHS or to_berth in TARGET_BERTHS:
                            ts = int(msg.get("time", 0)) / 1000
                            utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)
                            uk_dt = utc_dt.astimezone(TIMEZONE_LONDON)
                            time_str = uk_dt.strftime("%H:%M:%S")

                            print("=" * 60)
                            print(f"🚆 TRAIN! [{time_str}]")
                            print(f"   Headcode: {headcode}")
                            print(
                                f"   Area: {area_id} | Movement: Berth {from_berth} ---> Berth {to_berth}"
                            )
                            print("=" * 60 + "\n")

        except Exception as e:
            print(f"Parsing error: {e}", file=sys.stderr)

    def on_error(self, frame):
        print(f"received an error {frame.body}")

    def on_disconnected(self):
        print("disconnected")


if __name__ == "__main__":
    with open("secrets.json") as f:
        secrets = json.load(f)
        feed_username = secrets["username"] if isinstance(secrets, dict) else secrets[0]
        feed_password = secrets["password"] if isinstance(secrets, dict) else secrets[1]

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--durable", action="store_true")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--td", action="store_true", default=True)
    action.add_argument("--trust", action="store_true")

    args = parser.parse_args()

    HOST = "publicdatafeeds.networkrail.co.uk"
    PORT = 61618

    connection = stomp.Connection12(
        [(HOST, PORT)], keepalive=True, heartbeats=(5000, 5000)
    )
    connection.set_listener("", Listener(connection, durable=args.durable))

    connect_headers = {
        "username": feed_username,
        "passcode": feed_password,
        "wait": True,
    }
    if args.durable:
        connect_headers["client-id"] = feed_username

    connection.connect(**connect_headers)

    topic = "/topic/TRAIN_MVT_ALL_TOC" if args.trust else "/topic/TD_ALL_SIG_AREA"

    subscribe_headers = {"destination": topic, "id": 1}
    if args.durable:
        subscribe_headers.update(
            {
                "activemq.subscriptionName": feed_username + topic,
                "ack": "client-individual",
            }
        )
    else:
        subscribe_headers["ack"] = "auto"

    connection.subscribe(**subscribe_headers)

    try:
        while connection.is_connected():
            sleep(1)
    except KeyboardInterrupt:
        print("\nDisconnecting...")
        connection.disconnect()
