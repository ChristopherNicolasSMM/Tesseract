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
import json
from sqlalchemy import event, inspect

from core.db import db
from annotations import (
    label,
    plural,
    required,
    weak_ref,
    enum_field,
    field_labels,
    readonly_fields,
)


@label("Dispositivo Emulado")
@plural("emulated_devices")
@enum_field(
    "emulation_mode",
    options=[("sine_wave", "Onda senoidal"), ("random_walk", "Variação aleatória"), ("manual", "Manual")],
)
@field_labels({"functions_config": "Configuração das funções (JSON)"})
@readonly_fields(["is_running", "last_published_at"])
@required("emulation_mode", message="Modo de emulação é obrigatório")
@weak_ref("device_id",
          resolver="addons.addon_device_manager.root.services.device_metadata_lookup.get_device_metadata",
          options="device_metadatas")
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


@event.listens_for(EmulatedDevice, "before_insert")
@event.listens_for(EmulatedDevice, "before_update")
def validate_emulation_mode(mapper, connection, target):
    state = inspect(target)
    if state.pending or state.attrs.functions_config.history.has_changes():
        raw_config = target.functions_config
        if raw_config is None:
            raw_config = {}
        if isinstance(raw_config, str):
            try:
                raw_config = json.loads(raw_config) if raw_config.strip() else {}
            except json.JSONDecodeError as exc:
                raise ValueError("Configuração das funções precisa ser um JSON válido.") from exc
        if not isinstance(raw_config, dict):
            raise ValueError("Configuração das funções precisa ser um objeto JSON.")
        target.functions_config = raw_config
    if state.pending or state.attrs.emulation_mode.history.has_changes():
        if state.pending and target.emulation_mode is None:
            target.emulation_mode = "sine_wave"
        if target.emulation_mode not in {"sine_wave", "random_walk", "manual"}:
            raise ValueError("Modo de emulação inválido. Selecione uma opção da lista.")
