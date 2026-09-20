from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template
from train_tracker.models import TrainEvent, db
from train_tracker import utils

home = Blueprint("home", __name__)


def get_events():
    raw_events = TrainEvent.query.order_by(TrainEvent.timestamp.desc()).all()
    events = [e.to_dict() for e in raw_events]

    for event in events:
        if "date" not in event or not event["date"]:
            if event.get("timestamp"):
                ts = str(event["timestamp"])
                event["date"] = ts.split("T")[0].split(" ")[0]

    return events


@home.route("/")
def index():
    events = get_events()
    pagination = utils.paginate(events)
    paginated_train = pagination["items"]

    train_count_for_days = utils.train_count_for_days(events)
    categorised_trains = utils.categorised_trains(paginated_train)

    return render_template(
        "home/live_train_tracker.html",
        categorised_trains=categorised_trains,
        train_count_for_days=dict(train_count_for_days),
        page=pagination["page"],
        total_pages=pagination["total_pages"],
        today=date.today(),
    )


@home.route("/events/recent", methods=["GET"])
def get_recent_events():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    TrainEvent.query.filter(TrainEvent.timestamp < cutoff).delete()
    db.session.commit()

    events = get_events()
    daily_counts = utils.train_count_for_days(events)
    pagination = utils.paginate(events)

    return jsonify({
        "items": pagination["items"],
        "counts": dict(daily_counts),
        "page": pagination["page"],
        "total_pages": pagination["total_pages"]
    })