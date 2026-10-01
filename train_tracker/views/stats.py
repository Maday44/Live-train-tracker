from flask import Blueprint, render_template
from datetime import datetime, timezone
from train_tracker.models import StationSchedule
from train_tracker.utils.full_schedule import fetch_and_save_tilbury_schedule

stats = Blueprint("stats", __name__)


@stats.route("/stats")
def main_stats():
    return render_template(
        "statics/stats.html",
    )

@stats.route("/trainschedule")
def train_schedule():
    try:
        fetch_and_save_tilbury_schedule()
    except Exception as e:
        stats.logger.error(f"RTT Fetch Error: {e}")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    schedules = StationSchedule.query.filter(
        StationSchedule.crs_code == "TIL",
        StationSchedule.scheduled_time >= today_start
    ).order_by(StationSchedule.scheduled_time.asc()).all()


    trains = [s.to_dict() for s in schedules]

    return render_template("statics/train_schedule.html", trains=trains)

