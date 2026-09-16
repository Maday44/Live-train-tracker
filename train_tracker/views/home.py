from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template
from train_tracker.models import *

home = Blueprint("home", __name__)


@home.route("/")
def index():
    raw_events = TrainEvent.query.order_by(TrainEvent.timestamp.desc()).all()
    
    grouped_events = defaultdict(list)
    for event in raw_events:
        event_dict = event.to_dict()
        grouped_events[event_dict["date"]].append(event_dict)

    return render_template("home/live_train_tracker_home.html", grouped_events=grouped_events)



# json of the train data
@home.route("/events/recent", methods=["GET"])
def get_recent_events():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    TrainEvent.query.filter(TrainEvent.timestamp < cutoff).delete()
    db.session.commit()

    events = TrainEvent.query.order_by(TrainEvent.timestamp.desc()).all()
    return jsonify([event.to_dict() for event in events])
