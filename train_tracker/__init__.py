import json
import threading
from datetime import datetime
from datetime import timezone as dt_timezone

import stomp
from flask import Flask
from .models import TrainEvent
from train_tracker.models import db
from pytz import timezone
import os
from flask_migrate import Migrate


TIMEZONE_LONDON = timezone("Europe/London")
TARGET_AREAS = ["Q6"]
TARGET_BERTHS = ["0684", "0685"]


app = Flask(__name__)
migrate = Migrate(app, db)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", 
    "postgresql://trainwatch:trainwatch_password@db:5432/trainwatch"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app) 

with app.app_context():

    db.create_all()

class StompListener(stomp.ConnectionListener):
    def __init__(self, flask_app):
        self.app = flask_app
    """
    [RECEIVED CA_MSG]
  msg_type: CA
  area_id: NX
  time: 1789058323000
  from: 0218
  to: 0216
  descr: 9H47
    """

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

                    if area_id in TARGET_AREAS and (
                        from_berth in TARGET_BERTHS or to_berth in TARGET_BERTHS
                    ):
                        # time come in long int like 1789058323000 need to converted to uk time
                        ts = int(msg.get("time", 0)) / 1000
                        utc_dt = datetime.fromtimestamp(ts, dt_timezone.utc)

                        # Write to SQLite DB within Flask Context
                        with self.app.app_context():
                            event = TrainEvent(
                                headcode=headcode,
                                area=area_id,
                                from_berth=from_berth,
                                to_berth=to_berth,
                                timestamp=utc_dt,
                            )
                            db.session.add(event)
                            db.session.commit()
                        print(
                            f"SAVED: {headcode} [{area_id}] {from_berth} ---> {to_berth}"
                        )
        except Exception as e:
            print(f"STOMP error: {e}")


def start_stomp(flask_app):
    with open("secrets.json") as f:
        secrets = json.load(f)
    username = secrets["username"] if isinstance(secrets, dict) else secrets[0]
    password = secrets["password"] if isinstance(secrets, dict) else secrets[1]

    conn = stomp.Connection12(
        [("publicdatafeeds.networkrail.co.uk", 61618)],
        keepalive=True,
        heartbeats=(5000, 5000),
    )
    conn.set_listener("train_listener", StompListener(flask_app))
    conn.connect(username=username, passcode=password, wait=True)
    conn.subscribe(destination="/topic/TD_ALL_SIG_AREA", id=1, ack="auto")


threading.Thread(target=start_stomp, args=(app,), daemon=True).start()


from train_tracker.views.home import home  # noqa E402

app.register_blueprint(home)
