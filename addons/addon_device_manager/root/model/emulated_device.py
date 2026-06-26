"""
addons/addon_brewstation/features/feature_device_manager/model/emulated_device.py

Dispositivo emulado — simula leituras/escritas sem hardware real
(sine wave, random walk, manual), útil pra testar antes de ter o
equipamento físico.

Correção em relação ao original: `functions_config = Column(JSON,
default={})` usava um dict mutável como default — todas as instâncias
sem valor explícito compartilhariam o MESMO dict em memória (bug
clássico do Python, não do SQLAlchemy). Trocado por
`default=lambda: {}` (uma fábrica nova por instância, padrão já usado
em todo o resto do Tesseract).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Dispositivo Emulado")
@plural("emulated_devices")
@required("emulation_mode", message="Modo de emulação é obrigatório")
class EmulatedDevice(db.Model):
    __tablename__ = "emulated_device"

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(db.Integer, db.ForeignKey("device.id", ondelete="CASCADE"), nullable=False)
    device = db.relationship("DeviceMetadata", backref=db.backref("emulations", lazy=True))

    is_running = db.Column(db.Boolean, default=False, nullable=False)
    emulation_mode = db.Column(db.String(50), default="sine_wave", nullable=False)  # sine_wave, random_walk, manual

    functions_config = db.Column(db.JSON, default=lambda: {})  # corrigido: era default={} (mutável compartilhado)

    publish_interval_seconds = db.Column(db.Integer, default=5, nullable=False)
    last_published_at = db.Column(db.DateTime, nullable=True)

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
            "is_running": self.is_running,
            "emulation_mode": self.emulation_mode,
            "functions_config": self.functions_config or {},
            "publish_interval_seconds": self.publish_interval_seconds,
            "last_published_at": self.last_published_at.isoformat() if self.last_published_at else None,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<EmulatedDevice device_id={self.device_id} mode={self.emulation_mode}>"
