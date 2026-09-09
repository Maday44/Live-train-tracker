import json
import threading
from datetime import datetime, timezone as dt_timezone
from pytz import timezone
from flask import Flask
import stomp

from models import db, TrainEvent


TIMEZONE_LONDON = timezone("Europe/London")
TARGET_AREAS = ["Q6"]
TARGET_BERTHS = ["0684", "0685"]


app = Flask(__name__)

class StompListener(stomp.ConnectionListener):
    def __init__(self, flask_app):
        self.app = flask_app

    def on_message(self, frame):
        try:
            parsed_body = json.loads(frame.body)
            for outer in parsed_body:
                msg = list(outer.values())[0]
                if msg.get("msg_type") in ["CA", "CB", "CC"]:
                    area_id = msg.get("area_id", "")
                    from_berth = msg.get("from", "")
                    to_berth = msg.get("to", "")
                    headcode = msg.get("descr", "TRAIN")

                    if area_id in TARGET_AREAS and (from_berth in TARGET_BERTHS or to_berth in TARGET_BERTHS):
                        ts = int(msg.get("time", 0)) / 1000
                        utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)

                        # Write to SQLite DB within Flask Context
                        with self.app.app_context():
                            event = TrainEvent(
                                headcode=headcode,
                                area=area_id,
                                from_berth=from_berth,
                                to_berth=to_berth,
                                timestamp=utc_dt
                            )
                            db.session.add(event)
                            db.session.commit()
                        print(f"🚆 SAVED: {headcode} [{area_id}] {from_berth} ---> {to_berth}")
        except Exception as e:
            print(f"STOMP error: {e}")

def start_stomp(flask_app):
    with open("secrets.json") as f:
        secrets = json.load(f)
    username = secrets["username"] if isinstance(secrets, dict) else secrets[0]
    password = secrets["password"] if isinstance(secrets, dict) else secrets[1]

    conn = stomp.Connection12([("publicdatafeeds.networkrail.co.uk", 61618)], keepalive=True, heartbeats=(5000, 5000))
    conn.set_listener('train_listener', StompListener(flask_app))
    conn.connect(username=username, passcode=password, wait=True)
    conn.subscribe(destination="/topic/TD_ALL_SIG_AREA", id=1, ack='auto')


threading.Thread(target=start_stomp, args=(app,), daemon=True).start()


from train_tracker.views.home import home  # noqa E402

app.register_blueprint(home)
