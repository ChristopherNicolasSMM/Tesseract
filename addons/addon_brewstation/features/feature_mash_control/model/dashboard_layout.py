"""
addons/addon_brewstation/features/feature_mash_control/model/dashboard_layout.py

Layout de dashboard visual (canvas configurável). Pode se sobrepor
conceitualmente com o futuro Designer (Fase 7, herdado do
DEVStationFlask) — mantido aqui por ora porque é o que o BrewStation
original tinha; reavaliar quando a Fase 7 chegar.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Layout de Dashboard")
@plural("dashboard_layouts")
@required("name", message="Nome do layout é obrigatório")
class DashboardLayout(db.Model):
    __tablename__ = "layout"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    is_standby_enabled = db.Column(db.Boolean, default=False, nullable=False)
    standby_duration_seconds = db.Column(db.Integer, default=30, nullable=True)
    canvas_width = db.Column(db.Integer, default=1600, nullable=True)
    canvas_height = db.Column(db.Integer, default=900, nullable=True)
    background_color = db.Column(db.String(20), default="#0f1117", nullable=True)
    background_image_url = db.Column(db.String(500), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    layout_data = db.Column(db.Text, nullable=True)  # JSON dos elementos (compatibilidade)

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
            "description": self.description,
            "is_default": self.is_default,
            "is_standby_enabled": self.is_standby_enabled,
            "standby_duration_seconds": self.standby_duration_seconds,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "background_color": self.background_color,
            "background_image_url": self.background_image_url,
            "user_id": self.user_id,
            "layout_data": self.layout_data,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<DashboardLayout {self.name}>"
