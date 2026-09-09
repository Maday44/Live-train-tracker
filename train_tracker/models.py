from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class TrainEvent(db.Model):
    __tablename__ = "train_events"

    id = db.Column(db.Integer, primary_key=True)
    headcode = db.Column(db.String(10), nullable=False)
    area = db.Column(db.String(10), nullable=False)
    from_berth = db.Column(db.String(10), nullable=False)
    to_berth = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "headcode": self.headcode,
            "area": self.area,
            "from_berth": self.from_berth,
            "to_berth": self.to_berth,
            "time": self.timestamp.strftime("%H:%M:%S"),
        }
