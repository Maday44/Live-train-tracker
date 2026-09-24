from flask import Blueprint, render_template

stats = Blueprint("stats", __name__)


@stats.route("/stats")
def main_stats():
    return render_template(
        "statics/stats.html",
    )

@stats.route("/trainschedule")
def train_schedule():
    return render_template(
        "statics/train_schedule.html",
    )
