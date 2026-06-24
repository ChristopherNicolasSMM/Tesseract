"""
addons/addon_brewstation/features/feature_mash_control/model/brew_plant.py

Planta física de brassagem (conjunto de vasilhames). Sem FK — raiz
desta leva.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Planta de Brassagem")
@plural("brew_plants")
@required("name", message="Nome da planta é obrigatório")
class BrewPlant(db.Model):
    __tablename__ = "plant"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    capacity_liters = db.Column(db.Float, default=20.0, nullable=True)
    vessel_count = db.Column(db.Integer, default=1, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    plant_schema_json = db.Column(db.JSON, default=lambda: {})

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
            "capacity_liters": self.capacity_liters,
            "vessel_count": self.vessel_count,
            "is_active": self.is_active,
            "plant_schema_json": self.plant_schema_json or {},
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewPlant {self.name}>"
