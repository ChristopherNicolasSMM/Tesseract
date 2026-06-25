"""
model/core/field_rule.py

tesseract_field_rule — anexa uma regra do catálogo
(core/rules_catalog.py) a um campo de uma entidade qualquer. Mesmo
princípio de `tesseract_user_list_preference`: `entity_key` é só uma
string (o `plural` da entidade), nunca FK — Core não pode referenciar
tabela de domínio.

Nesta fase, só regras do grupo "Validação" têm efeito real (motor em
`static/js/rule_engine.js`) — anexar uma regra de Visibilidade/Cálculo
é permitido (o catálogo existe), mas não faz nada ainda, já que
dependem de um canvas com IDs de componente que só existirá no
Designer (Fase 7c). Ver `core/rules_catalog.py`.
"""
from datetime import datetime, timezone

from core.db import db


class FieldRule(db.Model):
    __tablename__ = "tesseract_field_rule"

    id = db.Column(db.Integer, primary_key=True)

    entity_key = db.Column(db.String(150), nullable=False, index=True)  # plural da entidade
    field_name = db.Column(db.String(150), nullable=False)
    rule_id = db.Column(db.String(50), nullable=False)  # id do catálogo (ex.: "obrigatorio")
    params_json = db.Column(db.JSON, default=lambda: {})
    order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_key": self.entity_key,
            "field_name": self.field_name,
            "rule_id": self.rule_id,
            "params_json": self.params_json or {},
            "order": self.order,
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return f"<FieldRule {self.entity_key}.{self.field_name} -> {self.rule_id}>"
