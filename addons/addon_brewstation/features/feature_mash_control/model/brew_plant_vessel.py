"""
addons/addon_brewstation/features/feature_mash_control/model/brew_plant_vessel.py

Vasilhame de uma planta (mash tun, boil kettle, fermenter...).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Vasilhame")
@plural("brew_plant_vessels")
@required("vessel_type", message="Tipo do vasilhame é obrigatório")
@required("label_text", message="Identificação do vasilhame é obrigatória")
class BrewPlantVessel(db.Model):
    __tablename__ = "plant_vessel"

    id = db.Column(db.Integer, primary_key=True)

    plant_id = db.Column(db.Integer, db.ForeignKey("plant.id"), nullable=False)
    plant = db.relationship("BrewPlant", backref=db.backref("vessels", lazy=True, cascade="all, delete-orphan"))

    vessel_type = db.Column(db.String(50), nullable=False)  # mash_tun, boil_kettle, hlt, fermenter, bright_tank
    label_text = db.Column(db.String(100), nullable=False)  # "label" renomeado (colide com @label)
    position_order = db.Column(db.Integer, default=1, nullable=True)
    description = db.Column(db.Text, nullable=True)

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
            "plant_id": self.plant_id,
            "vessel_type": self.vessel_type,
            "label_text": self.label_text,
            "position_order": self.position_order,
            "description": self.description,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewPlantVessel {self.label_text} ({self.vessel_type})>"
