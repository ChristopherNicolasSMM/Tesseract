"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_storage_device.py

Dispositivo de armazenamento (freezer, geladeira) — portado de
plugin_yeast_bank/model/yeast_bank_models.py (BrewStation). Sem FK
(é a tabela "raiz" desta leva de migração — Fase 5b).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Dispositivo de Armazenamento")
@plural("yeast_storage_devices")
@required("name", message="Nome do dispositivo é obrigatório")
@max_length("name", 120)
class YeastStorageDevice(db.Model):
    __tablename__ = "storage_device"  # nome curto — CrudGen/ModuleManager aplicam o prefixo
                                       # (era "device", renomeado: colidia com DeviceMetadata
                                       # de feature_device_manager — nome curto deve ser único
                                       # em todo o Addon, não só na Feature, skill 02)

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    machcode = db.Column(db.String(40), nullable=True)
    device_type = db.Column(db.String(40), nullable=False, default="freezer")
    status = db.Column(db.String(30), nullable=False, default="active")
    description = db.Column(db.Text, nullable=True)
    brand = db.Column(db.String(120), nullable=True)
    model = db.Column(db.String(120), nullable=True)
    serial_number = db.Column(db.String(120), nullable=True)
    physical_location = db.Column(db.String(180), nullable=True)
    virtual_address = db.Column(db.String(180), nullable=True)

    target_temperature_c = db.Column(db.Float, nullable=True)
    temperature_min_c = db.Column(db.Float, nullable=True)
    temperature_max_c = db.Column(db.Float, nullable=True)
    current_temperature_c = db.Column(db.Float, nullable=True)
    last_temperature_at = db.Column(db.DateTime, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def status_badge(self) -> str:
        if self.is_deleted or self.status == "inactive":
            return "inactive"
        if self.current_temperature_c is None:
            return "no_data"
        if self.temperature_min_c is not None and self.current_temperature_c < self.temperature_min_c:
            return "alert_low"
        if self.temperature_max_c is not None and self.current_temperature_c > self.temperature_max_c:
            return "alert_high"
        return "ok"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "machcode": self.machcode,
            "device_type": self.device_type,
            "status": self.status,
            "description": self.description,
            "brand": self.brand,
            "model": self.model,
            "serial_number": self.serial_number,
            "physical_location": self.physical_location,
            "virtual_address": self.virtual_address,
            "target_temperature_c": self.target_temperature_c,
            "temperature_min_c": self.temperature_min_c,
            "temperature_max_c": self.temperature_max_c,
            "current_temperature_c": self.current_temperature_c,
            "last_temperature_at": self.last_temperature_at.isoformat() if self.last_temperature_at else None,
            "health_status": self.status_badge(),
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastStorageDevice {self.name}>"
