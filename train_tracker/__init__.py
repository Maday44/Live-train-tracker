import json
import os
import threading
from datetime import datetime
from datetime import timezone as dt_timezone

from flask import Flask
from flask_migrate import Migrate
import stomp
from pytz import timezone

from train_tracker.models import *

# TIMEZONE = timezone("Europe/London")

# All the information you want for the app to be 
with open("delete.json") as f:
    delete = json.load(f)
    username = delete["username"]
    password = delete["password"]
    host = delete["host"]
    port = delete["port"]
    target_berths = delete["target_berths"]
    area_code = delete["area_code"]



TARGET_AREA = area_code


TARGET_BERTHS = target_berths
"""
looking via this url: https://www.opentraintimes.com/maps/signalling/ 
you can find the numbers assciate with a particular
railway station. depending on the platforms add the platform you wnat information about 
"""
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
    def __init__(self, flask_app):
        self.app = flask_app

    def on_message(self, message):
        try:
            parsed_body = json.loads(message.body)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                msg_type = msg.get("msg_type", "")

                if msg_type in ["CA", "CB", "CC"]:
                    area_id = msg.get("area_id", "")
                    from_berth = msg.get("from", "")
                    to_berth = msg.get("to", "")
                    headcode = msg.get("descr", "TRAIN")


                    area_match = area_id in TARGET_AREA
                    berth_match = (
                        not TARGET_BERTHS
                        or from_berth in TARGET_BERTHS
                        or to_berth in TARGET_BERTHS
                    )

                    if area_match and berth_match:
                        ts = int(msg.get("time", 0)) / 1000
                        utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)

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
                                to_map.station_name
                                if to_map
                                else f"Berth {to_berth}"
                            )

                            event = TrainEvent(
                                headcode=headcode,
                                msg_type=msg_type,
                                area=area_id,
                                from_berth=from_berth,
                                to_berth=to_berth,
                                from_station_name=from_station,
                                to_station_name=to_station,
                                timestamp=utc_dt,
                            )
                            db.session.add(event)
                            db.session.commit()

                        print(
                            f"[SAVED {msg_type}] Headcode: {headcode} | Area: {area_id} | "
                            f"{from_station} ({from_berth}) ---> {to_station} ({to_berth})",
                            flush=True,
                        )
        except Exception as e:
            print(f"STOMP Error: {e}", flush=True)


def start_stomp(flask_app):
    try:
        conn = stomp.Connection12(
            [(host, port)],
            keepalive=True,
            heartbeats=(15000, 15000),
        )
        conn.set_listener("train_listener", StompListener(flask_app))
        conn.connect(username=username, passcode=password, wait=True)
        conn.subscribe(destination="/topic/TD_ALL_SIG_AREA", id=1, ack="auto")
        print("STOMP Listener successfully", flush=True)
    except Exception as err:
        print(f"STOMP Connection Failed: {err}", flush=True)


threading.Thread(target=start_stomp, args=(app,), daemon=True).start()

from train_tracker.views.home import home  # noqa E402

app.register_blueprint(home)