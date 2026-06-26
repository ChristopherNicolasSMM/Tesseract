"""
addons/addon_brewstation/features/feature_mash_control/model/brew_plant_mapping.py

Mapeia um "papel" (sensor de temperatura, atuador de aquecimento) de
um vasilhame a uma Function do addon_device_manager. NUNCA FK direta
entre Addons (skill 02) — referência fraca por `name` + chamada de
service (services.device_function_lookup.get_function_by_name).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Mapeamento de Equipamento")
@plural("brew_plant_mappings")
@required("role_key", message="Papel (role_key) é obrigatório")
class BrewPlantMapping(db.Model):
    __tablename__ = "plant_mapping"

    id = db.Column(db.Integer, primary_key=True)

    vessel_id = db.Column(db.Integer, db.ForeignKey("plant_vessel.id"), nullable=False)
    vessel = db.relationship("BrewPlantVessel", backref=db.backref("mappings", lazy=True, cascade="all, delete-orphan"))

    role_key = db.Column(db.String(50), nullable=False)  # sensor_temp, actor_heat...

    # Referência fraca (skill 02: nunca FK direta entre Addons) — resolver via
    # addon_device_manager.services.device_function_lookup.get_function_by_name().
    device_function_name = db.Column(db.String(100), nullable=False)

    label_text = db.Column(db.String(100), nullable=True)
    is_required = db.Column(db.Boolean, default=True, nullable=False)

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
            "vessel_id": self.vessel_id,
            "role_key": self.role_key,
            "device_function_name": self.device_function_name,
            "label_text": self.label_text,
            "is_required": self.is_required,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<BrewPlantMapping {self.role_key} vessel_id={self.vessel_id}>"
