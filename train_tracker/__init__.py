import json
import os
import threading
from datetime import datetime
from datetime import timezone as dt_timezone

from flask import Flask
from flask_migrate import Migrate
import stomp
from train_tracker.models import db, TrainEvent, BerthMap
from pytz import timezone
import time
from .utils.rtt import fetch_rtt_service

TIMEZONE_LONDON = timezone("Europe/London")

# Load config secrets
with open("secrets.json") as f:
    secrets = json.load(f)
    username = secrets["username"]
    password = secrets["password"]
    host = secrets["host"]
    port = secrets["port"]
    target_berths = secrets.get("target_berths", [])
    area_code = secrets.get("area_code", "")
    api_key = secrets["RTT_API_KEY"]


TARGET_AREAS = [area_code] if isinstance(area_code, str) else area_code
TARGET_BERTHS = target_berths

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://trainwatch:trainwatch_password@db:5432/trainwatch",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()


class StompListener(stomp.ConnectionListener):

    def __init__(self, flask_app, connection=None):
        self.app = flask_app
        self.conn = connection
        self.last_event = None

    def on_disconnected(self):
        print("STOMP disconnected! Triggering auto-reconnect...", flush=True)

    def on_error(self, frame):
        print(f"STOMP Protocol Error: {frame.body}", flush=True)

    def on_message(self, message):
        try:
            parsed_body = json.loads(message.body)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                msg_type = msg.get("msg_type", "")
                # message code are:
                if msg_type in ["CA", "CB", "CC"]:
                    area_id = msg.get("area_id", "").strip()
                    from_berth = msg.get("from", "").strip()
                    to_berth = msg.get("to", "").strip()
                    headcode = msg.get("descr", "").strip()
                    event_time = msg.get("time", 0)

                    event_key = (
                        f"{headcode}:{area_id}:{from_berth}:{to_berth}:{event_time}"
                    )

                    # Skip duplicate processing
                    if event_key == self.last_event:
                        continue
                    self.last_event = event_key

                    area_match = area_id in TARGET_AREAS
                    berth_match = (
                        not TARGET_BERTHS
                        or from_berth in TARGET_BERTHS
                        or to_berth in TARGET_BERTHS
                    )

                    if area_match and berth_match:
                        ts = int(msg.get("time", 0)) / 1000
                        utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)
                        uk_dt = utc_dt.astimezone(TIMEZONE_LONDON)

                        with self.app.app_context():
                            from_map = BerthMap.query.filter_by(
                                area=area_id, berth=from_berth
                            ).first()
                            to_map = BerthMap.query.filter_by(
                                area=area_id, berth=to_berth
                            ).first()

                            from_station = (
                                from_map.station_name
                                if from_map
                                else f"Berth {from_berth}"
                            )
                            to_station = (
                                to_map.station_name if to_map else f"Berth {to_berth}"
                            )
                            event_date_str = uk_dt.strftime("%Y-%m-%d")

                            rtt_info = fetch_rtt_service(
                                identifier=headcode,
                                date_str=event_date_str,
                                refresh_token=api_key,
                                location_code=from_station,
                                area_id=area_id,
                                is_uid=False,
                            )
                            service_uid = (
                                rtt_info.get("rtt_service_uid") if rtt_info else None
                            )
                            origin = rtt_info.get("origin") if rtt_info else None
                            destination = (
                                rtt_info.get("destination") if rtt_info else None
                            )

                            event = TrainEvent(
                                headcode=headcode,
                                msg_type=msg_type,
                                area=area_id,
                                from_berth=from_berth,
                                to_berth=to_berth,
                                from_station_name=from_station,
                                to_station_name=to_station,
                                rtt_service_uid=service_uid,  # e.g., 'G34120'
                                origin_station=origin,  # e.g., 'London Liverpool Street'
                                destination_station=destination,  # e.g., 'Southend Victoria'
                                timestamp=uk_dt,  # UK time uk_d
                            )
                            db.session.add(event)
                            db.session.commit()
                        # debug message
                        print(
                            f"Time {uk_dt} : [SAVED {msg_type}] Headcode: {headcode} | Area: {area_id} | "
                            f"{from_station} ({from_berth}) ---> {to_station} ({to_berth})",
                            flush=True,
                        )
        except Exception as e:
            print(f"STOMP Parsing Error: {e}", flush=True)


def start_stomp(flask_app):
    """Maintains a resilient background connection to Network Rail with auto-retry."""
    while True:
        try:
            print("Connecting to Network Rail STOMP feed...", flush=True)
            conn = stomp.Connection12(
                [(host, port)],
                keepalive=True,
                heartbeats=(15000, 15000),  # 15s
            )

            listener = StompListener(flask_app, connection=conn)
            conn.set_listener("train_listener", listener)

            conn.connect(username=username, passcode=password, wait=True)
            conn.subscribe(destination="/topic/TD_ALL_SIG_AREA", id=1, ack="auto")
            print(
                "STOMP Listener successfully connected to /topic/TD_ALL_SIG_AREA",
                flush=True,
            )

            while conn.is_connected():
                time.sleep(1)

        except Exception as err:
            print(
                f"STOMP Connection dropped/failed: {err}. Retrying in 10s...",
                flush=True,
            )
            time.sleep(10)


# makes sure that
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    threading.Thread(target=start_stomp, args=(app,), daemon=True).start()
    print("STOMP Listener thread started.", flush=True)

from train_tracker.views.home import home  # noqa E402

app.register_blueprint(home)
