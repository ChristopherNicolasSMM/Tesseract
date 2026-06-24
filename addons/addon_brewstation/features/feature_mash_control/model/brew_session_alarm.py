"""
addons/addon_brewstation/features/feature_mash_control/model/brew_session_alarm.py

Alarme disparado durante uma sessão.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Alarme da Sessão")
@plural("brew_session_alarms")
@required("message", message="Mensagem do alarme é obrigatória")
class BrewSessionAlarm(db.Model):
    __tablename__ = "session_alarm"

    id = db.Column(db.Integer, primary_key=True)

    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    session = db.relationship("BrewSession", backref=db.backref("alarms", lazy=True, cascade="all, delete-orphan"))

    alarm_type = db.Column(db.String(50), nullable=True)
    severity = db.Column(db.String(20), default="medium", nullable=False)  # low, medium, high, critical
    message = db.Column(db.String(500), nullable=False)
    is_acknowledged = db.Column(db.Boolean, default=False, nullable=False)

    acknowledged_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "alarm_type": self.alarm_type,
            "severity": self.severity,
            "message": self.message,
            "is_acknowledged": self.is_acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewSessionAlarm [{self.severity}] {self.message[:50]}>"
