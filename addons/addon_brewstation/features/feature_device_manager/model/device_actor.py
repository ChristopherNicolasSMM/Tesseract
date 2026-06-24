"""
addons/addon_brewstation/features/feature_device_manager/model/device_actor.py

Ator: associa uma porta de um device a uma função específica.

Nota sobre a melhoria em relação ao original: o BrewStation
desabilitava deliberadamente `relationship()` aqui, porque o
mecanismo de prefixo dele forçava configuração de mapper antes da
renomeação de tabela e quebrava o boot. No Tesseract isso foi testado
e confirmado funcionando (skill 02 + BACKLOG.md, Fase 5b) — o prefixo
é aplicado antes de `create_all()`/configuração de mapper, então
`relationship()` funciona normalmente aqui.
"""
import uuid
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Ator de Dispositivo")
@plural("device_actors")
@required("port_name", message="Nome da porta é obrigatório")
@required("actor_type", message="Tipo do ator é obrigatório (sensor/actuator/rule_trigger)")
class DeviceActor(db.Model):
    __tablename__ = "actor"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    device_id = db.Column(db.Integer, db.ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    device = db.relationship("DeviceMetadata", backref=db.backref("actors", lazy=True))

    port_name = db.Column(db.String(50), nullable=False)  # GPIO1, ADC0...
    function_id = db.Column(db.Integer, db.ForeignKey("function.id", ondelete="RESTRICT"), nullable=False, index=True)
    function = db.relationship("DeviceFunction", backref=db.backref("actors", lazy=True))

    actor_type = db.Column(db.String(20), nullable=False)  # sensor, actuator, rule_trigger
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)

    config_json = db.Column(db.Text, nullable=True)

    # Vínculo com entidades de outros Addons/Features (skill 02: nunca
    # FK direta entre módulos diferentes — guarda referência fraca por
    # nome + id, resolvida via service, nunca via ORM direto).
    plugin_name = db.Column(db.String(100), nullable=True, index=True)
    plugin_entity_id = db.Column(db.String(100), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def get_config(self) -> dict:
        import json
        if not self.config_json:
            return {}
        try:
            return json.loads(self.config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, config_dict: dict | None) -> None:
        import json
        self.config_json = json.dumps(config_dict, ensure_ascii=False) if config_dict else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "device_id": self.device_id,
            "port_name": self.port_name,
            "function_id": self.function_id,
            "actor_type": self.actor_type,
            "name": self.name,
            "description": self.description,
            "config": self.get_config(),
            "plugin_name": self.plugin_name,
            "plugin_entity_id": self.plugin_entity_id,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<DeviceActor {self.name} ({self.actor_type}) device_id={self.device_id}>"
