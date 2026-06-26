"""
addons/addon_brewstation/features/feature_mash_control/model/automation_rule.py

Definição de uma regra de automação (sensor -> condição -> ator).
Esta tabela é só a DEFINIÇÃO da regra (dados de configuração) — o
motor que avalia continuamente o sensor e dispara a ação
(services/automation_engine.py no BrewStation original) fica fora do
escopo desta fase (decisão registrada no BACKLOG.md).

Referência a DeviceFunction (addon_device_manager, Addon separado
após a promoção — ver docs/skills/05-proposta-addon-device-manager-e-mqtt.md):
NUNCA FK direta entre Addons (skill 02). Resolvida via referência
fraca por `name` (chave de negócio única e estável de DeviceFunction)
+ chamada de service público
(services.device_function_lookup.get_function_by_name), nunca por
FK/ORM/relationship cross-Addon.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Regra de Automação")
@plural("automation_rules")
@required("name", message="Nome da regra é obrigatório")
@required("condition_operator", message="Operador da condição é obrigatório")
class AutomationRule(db.Model):
    __tablename__ = "rule"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Condição — sensor. Referência fraca (skill 02: nunca FK direta
    # entre Addons) — resolver via
    # addon_device_manager.services.device_function_lookup.get_function_by_name().
    sensor_function_name = db.Column(db.String(100), nullable=False)
    sensor_metric = db.Column(db.String(50), default="temperature", nullable=True)
    condition_operator = db.Column(db.String(5), nullable=False)  # <=, >=, ==, !=, <, >
    condition_value = db.Column(db.Float, nullable=False)
    condition_unit = db.Column(db.String(20), default="°C", nullable=True)

    # Ação — ator. Mesma regra de referência fraca acima.
    actor_function_name = db.Column(db.String(100), nullable=False)
    actor_action = db.Column(db.String(20), nullable=False)  # ON, OFF, TOGGLE, SET_VALUE
    actor_value = db.Column(db.Float, nullable=True)

    cooldown_seconds = db.Column(db.Integer, default=30, nullable=True)
    last_triggered_at = db.Column(db.DateTime, nullable=True)
    trigger_count = db.Column(db.Integer, default=0, nullable=True)

    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=True)
    session = db.relationship("BrewSession", backref=db.backref("automation_rules", lazy=True))

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
            "is_active": self.is_active,
            "sensor_function_name": self.sensor_function_name,
            "sensor_metric": self.sensor_metric,
            "condition_operator": self.condition_operator,
            "condition_value": self.condition_value,
            "condition_unit": self.condition_unit,
            "actor_function_name": self.actor_function_name,
            "actor_action": self.actor_action,
            "actor_value": self.actor_value,
            "cooldown_seconds": self.cooldown_seconds,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "trigger_count": self.trigger_count,
            "session_id": self.session_id,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<AutomationRule {self.name}>"
