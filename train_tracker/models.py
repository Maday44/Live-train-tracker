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


class StationSchedule(db.Model):
    __tablename__ = "train_schedule"

    id = db.Column(db.Integer, primary_key=True)
    headcode = db.Column(db.String(10), nullable=False, index=True)
    rtt_service_uid = db.Column(db.String(20), nullable=False, index=True)

    crs_code = db.Column(db.String(5), nullable=False, default="TIL", index=True)
    origin_station = db.Column(db.String(100), nullable=True)
    destination_station = db.Column(db.String(100), nullable=True)

    is_cancelled = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20))
    delay_minutes = db.Column(db.Integer, default=0)
    scheduled_time = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    actual_time = db.Column(db.DateTime(timezone=True), nullable=True)
    msg_type = db.Column(db.String(10), nullable=True)
    area = db.Column(db.String(10), nullable=True)
    from_berth = db.Column(db.String(10), nullable=True)
    to_berth = db.Column(db.String(10), nullable=True)

    def to_dict(self):
        def format_uk_time(dt):
            if not dt:
                return None
            utc_dt = (
                dt.replace(tzinfo=timezone.utc)
                if dt.tzinfo is None
                else dt.astimezone(timezone.utc)
            )
            return utc_dt.astimezone(UK_TZ)

        sched_uk = format_uk_time(self.scheduled_time)
        actual_uk = format_uk_time(self.actual_time)

        return {
            "id": self.id,
            "headcode": self.headcode,
            "rtt_service_uid": self.rtt_service_uid,
            "origin": self.origin_station or "Unknown",
            "destination": self.destination_station or "Unknown",
            "scheduled_time": sched_uk.strftime("%H:%M") if sched_uk else None,
            "actual_time": actual_uk.strftime("%H:%M") if actual_uk else "N/A",
            "status": "CANCELLED" if self.is_cancelled else self.status,
            "delay_minutes": self.delay_minutes,
            "date": sched_uk.strftime("%Y-%m-%d") if sched_uk else None,
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


class TrainStationStatics(db.Model):
    """All the statics from the train stations that month"""

    __tablename__ = "train_station_statics"

    id = db.Column(db.Integer, primary_key=True)
    crs_code = db.Column(db.String(5), nullable=False, default="TIL", index=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    number_of_trains_pass = db.Column(db.Integer, default=0, nullable=False)
    number_of_trains_on_time = db.Column(db.Integer, default=0, nullable=False)
    number_of_trains_delayed = db.Column(db.Integer, default=0, nullable=False)
    number_of_trains_early = db.Column(db.Integer, default=0, nullable=False)
    number_of_trains_cancelled = db.Column(db.Integer, default=0, nullable=False)

    total_delay_minutes = db.Column(db.Integer, default=0, nullable=False)
    avg_delay_minutes = db.Column(db.Float, default=0.0)

    last_updated = db.Column(
        db.DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint("crs_code", "year", "month", name="uix_station_year_month"),
    )

    @property
    def on_time_percentage(self):
        """Calculates percentage of non-cancelled trains that ran on time."""
        effective_total = self.total_trains - self.number_of_trains_cancelled
        if effective_total <= 0:
            return 0.0
        return round((self.number_of_trains_on_time / effective_total) * 100, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "crs_code": self.crs_code,
            "period": f"{self.year}-{self.month:02d}",
            "year": self.year,
            "month": self.month,
            "total_trains": self.total_trains,
            "on_time": self.number_of_trains_on_time,
            "delayed": self.number_of_trains_delayed,
            "early": self.number_of_trains_early,
            "cancelled": self.number_of_trains_cancelled,
            "on_time_percentage": self.on_time_percentage,
            "total_delay_minutes": self.total_delay_minutes,
            "avg_delay_minutes": round(self.avg_delay_minutes, 1),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }