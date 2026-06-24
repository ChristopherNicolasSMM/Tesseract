"""
addons/addon_brewstation/features/feature_mash_control/model/brew_session_log.py

Log de eventos de uma sessão (info/warning/error/alarm).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Log da Sessão")
@plural("brew_session_logs")
@required("message", message="Mensagem do log é obrigatória")
class BrewSessionLog(db.Model):
    __tablename__ = "session_log"

    id = db.Column(db.Integer, primary_key=True)

    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    session = db.relationship("BrewSession", backref=db.backref("logs", lazy=True, cascade="all, delete-orphan"))

    step_id = db.Column(db.Integer, db.ForeignKey("session_step.id"), nullable=True)
    step = db.relationship("BrewSessionStep", backref=db.backref("logs", lazy=True))

    log_level = db.Column(db.String(20), default="info", nullable=False)  # info, warning, error, alarm
    source = db.Column(db.String(50), nullable=True)  # pid_engine, automation, user, sensor
    message = db.Column(db.String(500), nullable=False)
    detail_json = db.Column(db.JSON, default=lambda: {})

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "step_id": self.step_id,
            "log_level": self.log_level,
            "source": self.source,
            "message": self.message,
            "detail_json": self.detail_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewSessionLog [{self.log_level}] {self.message[:50]}>"
