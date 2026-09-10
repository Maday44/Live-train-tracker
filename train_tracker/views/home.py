from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template
from train_tracker.models import *

home = Blueprint("home", __name__)


@home.route("/")
def index():
    return render_template("live_train_tracker_home.html")


# json of the train data
@home.route("/events/recent", methods=["GET"])
def get_recent_events():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    TrainEvent.query.filter(TrainEvent.timestamp < cutoff).delete()
    db.session.commit()

    events = TrainEvent.query.order_by(TrainEvent.timestamp.desc()).all()
    return jsonify([event.to_dict() for event in events])
