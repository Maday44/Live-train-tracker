from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")
db = SQLAlchemy()


class TrainEvent(db.Model):
    __tablename__ = "train_events"

    id = db.Column(db.Integer, primary_key=True)
    headcode = db.Column(db.String(10), nullable=False, index=True)
    msg_type = db.Column(db.String(5), nullable=False)  # CA, CB, CC
    area = db.Column(db.String(10), nullable=False)
    from_berth = db.Column(db.String(10), nullable=False)
    to_berth = db.Column(db.String(10), nullable=False)
    from_station_name = db.Column(db.String(100), nullable=True)
    to_station_name = db.Column(db.String(100), nullable=True)
    rtt_service_uid = db.Column(db.String(20), nullable=True)
    origin_station = db.Column(db.String(100), nullable=True)
    destination_station = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def to_dict(self):
        utc_dt = (
            self.timestamp.replace(tzinfo=timezone.utc)
            if self.timestamp.tzinfo is None
            else self.timestamp.astimezone(timezone.utc)
        )

        uk_dt = utc_dt.astimezone(UK_TZ)

        iso_timestamp = uk_dt.isoformat()
        time_str = uk_dt.strftime("%H:%M:%S")
        date_str = uk_dt.strftime("%Y-%m-%d")

        return {
            "id": self.id,
            "headcode": self.headcode,
            "msg_type": self.msg_type,
            "area": self.area,
            "from_berth": self.from_berth,
            "to_berth": self.to_berth,
            "from_station": self.from_station_name,
            "to_station": self.to_station_name,
            "rtt_service_uid": self.rtt_service_uid,
            "origin": self.origin_station or "Unknown",
            "destination": self.destination_station or "Unknown",
            "time": time_str,
            "date": date_str,
            "timestamp": iso_timestamp,
        }


class BerthMap(db.Model):
    """Maps signaling area + berth ID to human-readable station names."""

    __tablename__ = "berth_maps"

    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(10), nullable=False, index=True)
    berth = db.Column(db.String(10), nullable=False, index=True)
    station_name = db.Column(db.String(100), nullable=False)
    tiploc = db.Column(db.String(20), nullable=True)  # Railway timing point code

    __table_args__ = (db.UniqueConstraint("area", "berth", name="unique_area_berth"),)


class Service(db.Model):
    """Caches origin, destination, and schedule info retrieved from RTT API."""

    __tablename__ = "service_cache"

    id = db.Column(db.Integer, primary_key=True)
    headcode = db.Column(db.String(10), nullable=False, index=True)
    run_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    rtt_service_uid = db.Column(db.String(20), nullable=False, unique=True)
    origin_name = db.Column(db.String(100), nullable=False)
    origin_dep_time = db.Column(db.String(10), nullable=False)  # e.g. "14:15"
    destination_name = db.Column(db.String(100), nullable=False)
    destination_arr_time = db.Column(db.String(10), nullable=False)  # e.g. "15:02"

    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "headcode": self.headcode,
            "rtt_service_uid": self.rtt_service_uid,
            "origin": self.origin_name,
            "started_at": self.origin_dep_time,
            "destination": self.destination_name,
            "expected_at": self.destination_arr_time,
        }
