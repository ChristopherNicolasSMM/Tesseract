"""
addons/addon_brewstation/features/feature_device_manager/model/device_metadata.py

Metadados de dispositivo IoT — banco guarda só o essencial;
configuração detalhada/estado vivem em JSON em disco (padrão já usado
no BrewStation original, preservado aqui).

PK Integer + external_id UUID (skill 02, "Regra de PK externa") —
o BrewStation original usava UUID como PK; aqui o UUID vira
external_id, exposto a sistemas externos (broker MQTT etc.), e o
`id` interno é Integer como toda outra tabela do Tesseract.
"""
import uuid
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Dispositivo IoT")
@plural("device_metadatas")
@required("name", message="Nome do dispositivo é obrigatório")
@max_length("name", 100)
class DeviceMetadata(db.Model):
    __tablename__ = "device"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    name = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(50), nullable=True)  # sensor, actuator, gateway
    protocol = db.Column(db.String(20), nullable=True)  # mqtt, http, websocket
    config_path = db.Column(db.String(500), nullable=True)  # JSON de config em disco
    state_path = db.Column(db.String(500), nullable=True)  # JSON de estado em disco
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    port_config = db.Column(db.Text, nullable=True)  # JSON serializado (GPIO, entradas/saídas)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def get_port_config(self) -> dict:
        import json
        if not self.port_config:
            return {}
        try:
            return json.loads(self.port_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_port_config(self, config_dict: dict | None) -> None:
        import json
        self.port_config = json.dumps(config_dict, ensure_ascii=False) if config_dict else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "name": self.name,
            "device_type": self.device_type,
            "protocol": self.protocol,
            "config_path": self.config_path,
            "state_path": self.state_path,
            "is_active": self.is_active,
            "port_config": self.get_port_config(),
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<DeviceMetadata {self.name} ({self.device_type})>"
