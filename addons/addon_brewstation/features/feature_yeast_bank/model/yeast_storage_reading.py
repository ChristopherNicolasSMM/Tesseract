"""
addons/addon_brewstation/features/feature_yeast_bank/model/yeast_storage_reading.py

Leitura de temperatura/umidade de um dispositivo — FK para
YeastStorageDevice (mesma Feature, permitido pela skill 02).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Leitura de Armazenamento")
@plural("yeast_storage_readings")
@required("temperature_c", message="Temperatura é obrigatória")
class YeastStorageReading(db.Model):
    __tablename__ = "reading"

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(db.Integer, db.ForeignKey("storage_device.id"), nullable=False)
    device = db.relationship("YeastStorageDevice", backref=db.backref("readings", lazy=True))

    recorded_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    temperature_c = db.Column(db.Float, nullable=False)
    humidity_percent = db.Column(db.Float, nullable=True)
    source_type = db.Column(db.String(30), nullable=False, default="manual")
    source_ref = db.Column(db.String(120), nullable=True)
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
            "device_id": self.device_id,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "temperature_c": self.temperature_c,
            "humidity_percent": self.humidity_percent,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "notes": self.notes,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<YeastStorageReading device_id={self.device_id} {self.temperature_c}°C>"
