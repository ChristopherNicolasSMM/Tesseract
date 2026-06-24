"""
addons/addon_brewstation/features/feature_mash_control/model/brew_session_step.py

Passo de uma sessão. Os campos `pid_*` são só PARÂMETROS configurados
(ex.: Kp/Ki/Kd) — o loop de controle PID que de fato os usa em tempo
real fica fora do escopo desta fase.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Passo da Sessão")
@plural("brew_session_steps")
@required("name", message="Nome do passo é obrigatório")
class BrewSessionStep(db.Model):
    __tablename__ = "session_step"

    id = db.Column(db.Integer, primary_key=True)

    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False)
    session = db.relationship("BrewSession", backref=db.backref("steps", lazy=True, cascade="all, delete-orphan"))

    step_index = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    step_type = db.Column(db.String(50), nullable=True)

    target_temp = db.Column(db.Float, nullable=True)
    duration_seconds = db.Column(db.Integer, default=0, nullable=True)

    vessel_id = db.Column(db.Integer, db.ForeignKey("plant_vessel.id"), nullable=True)
    vessel = db.relationship("BrewPlantVessel", backref=db.backref("session_steps", lazy=True))

    pid_enabled = db.Column(db.Boolean, default=False, nullable=False)
    pid_kp = db.Column(db.Float, default=1.0, nullable=True)
    pid_ki = db.Column(db.Float, default=0.0, nullable=True)
    pid_kd = db.Column(db.Float, default=0.0, nullable=True)

    hop_addition_json = db.Column(db.JSON, default=lambda: [])

    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, active, completed, skipped
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    actual_duration_s = db.Column(db.Integer, default=0, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "step_index": self.step_index,
            "name": self.name,
            "step_type": self.step_type,
            "target_temp": self.target_temp,
            "duration_seconds": self.duration_seconds,
            "vessel_id": self.vessel_id,
            "pid_enabled": self.pid_enabled,
            "pid_kp": self.pid_kp,
            "pid_ki": self.pid_ki,
            "pid_kd": self.pid_kd,
            "hop_addition_json": self.hop_addition_json or [],
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<BrewSessionStep {self.name} session_id={self.session_id}>"
