"""
addons/addon_brewstation/features/feature_mash_control/model/brew_session.py

Sessão de brassagem — representa UMA execução de processo. O campo
`status`/`current_step_index` é só armazenamento de estado; o motor
que de fato avança a sessão (engine/process/mash_process_engine.py no
BrewStation original) fica fora do escopo desta fase (decisão
registrada no BACKLOG.md — Fase 6 é só CRUD).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices


@label("Sessão de Brassagem")
@plural("brew_sessions")
@choices("status", label="Status")
@required("name", message="Nome da sessão é obrigatório")
class BrewSession(db.Model):
    __tablename__ = "session"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    plant_id = db.Column(db.Integer, db.ForeignKey("plant.id"), nullable=True)
    plant = db.relationship("BrewPlant", backref=db.backref("sessions", lazy=True))

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"), nullable=True)
    recipe = db.relationship("MashRecipe", backref=db.backref("sessions", lazy=True))

    status = db.Column(db.String(20), default="draft", nullable=False)  # draft, active, paused, completed, aborted
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    current_step_index = db.Column(db.Integer, default=0, nullable=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)

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
            "name": self.name,
            "plant_id": self.plant_id,
            "recipe_id": self.recipe_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
            "current_step_index": self.current_step_index,
            "operator_id": self.operator_id,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewSession {self.name} status={self.status}>"
