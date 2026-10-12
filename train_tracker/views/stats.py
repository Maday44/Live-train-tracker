from flask import Blueprint, render_template, current_app
from train_tracker.models import db,StationSchedule
from train_tracker.utils.full_schedule import fetch_and_save_tilbury_schedule
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

stats = Blueprint("stats", __name__)


@stats.route("/stats")
def main_stats():
    return render_template(
        "statics/stats.html",
    )

LONDON = ZoneInfo("Europe/London")
 
 
def _uk_hhmm(dt):
    """UTC (or naive-UTC) datetime -> 'HH:MM' in UK time, or None."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LONDON).strftime("%H:%M")
 
 
@stats.route("/trainschedule")
def train_schedule():
    try:
        fetch_and_save_tilbury_schedule(force=True, include_buses=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"RTT Fetch Error: {e}")

    today = datetime.now(LONDON).date()
    
    start_local = datetime.combine(today, time.min, tzinfo=LONDON)
    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    schedules = (
        StationSchedule.query.filter(
            StationSchedule.crs_code == "TIL",
            StationSchedule.scheduled_time >= start_utc,
            StationSchedule.scheduled_time < end_utc,
        )
        .order_by(StationSchedule.scheduled_time.asc())
        .all()
    )

    trains = [
        {
            "headcode": s.headcode,
            "scheduled_time": _uk_hhmm(s.scheduled_time),
            "actual_time": _uk_hhmm(s.actual_time),
            "origin": s.origin_station,
            "destination": s.destination_station,
            "status": s.status,
            "delay_minutes": s.delay_minutes or 0,
            "is_cancelled": bool(s.is_cancelled),
        }
        for s in schedules
    ]

    return render_template("statics/train_schedule.html", trains=trains)