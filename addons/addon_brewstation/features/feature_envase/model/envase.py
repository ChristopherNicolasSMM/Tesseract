"""
addons/addon_brewstation/features/feature_envase/model/envase.py

Evento de empacotamento de um Lote (BrewSession, feature_mash_control).
`lote_id` e FK real (mesmo Addon, cross-Feature - skill 02 permite).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices, min_value, enum_field, weak_ref, readonly_fields

_MATERIAL_RESOLVER = "addons.addon_estoque.root.services.material_lookup.get_material"


@label("Envase")
@plural("envases")
@readonly_fields(["componentes_snapshot", "estorno_snapshot", "cancelado_em", "motivo_cancelamento", "cancelado_por_id"])
@enum_field("status", options=["registrado", "cancelado"])
@choices("status", label="Status")
@required("lote_id", message="Lote é obrigatório")
@min_value("quantidade_litros", 0, message="Quantidade não pode ser negativa")
@weak_ref("material_resultante_id", resolver=_MATERIAL_RESOLVER, options="materials")
@weak_ref("lote_id",
          resolver="addons.addon_brewstation.features.feature_mash_control.services.mash_control_lookups.get_session",
          options="brew_sessions")
class Envase(db.Model):
    __crudgen_immutable__ = True
    __crudgen_no_delete__ = True
    __tablename__ = "envase"

    id = db.Column(db.Integer, primary_key=True)

    lote_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False, index=True)
    lote = db.relationship("BrewSession", backref=db.backref("envases", lazy=True))

    # Skill 26 — Material acabado que este Envase representa (ex.:
    # "Growler 1L Valirian Pilsen"). Referência fraca (SEM FK,
    # addon_estoque, skill 02) — nullable por enquanto pra não quebrar
    # Envase já existentes, criados antes desta coluna existir.
    material_resultante_id = db.Column(db.Integer, nullable=True, index=True)

    quantidade_litros = db.Column(db.Float, nullable=True)
    # Fotografia dos componentes e custos na confirmação; nulo em envases antigos.
    componentes_snapshot = db.Column(db.JSON, nullable=True)
    estorno_snapshot = db.Column(db.JSON, nullable=True)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    motivo_cancelamento = db.Column(db.Text, nullable=True)
    cancelado_por_id = db.Column(db.Integer, nullable=True)
    data_envase = db.Column(db.Date, nullable=True)
    tipo_envase = db.Column(db.String(30), nullable=True)  # garrafa, barril, lata, ...
    status = db.Column(db.String(20), nullable=False, default="registrado")  # registrado, cancelado

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lote_id": self.lote_id,
            "material_resultante_id": self.material_resultante_id,
            "quantidade_litros": self.quantidade_litros,
            "componentes_snapshot": self.componentes_snapshot,
            "estorno_snapshot": self.estorno_snapshot,
            "cancelado_em": self.cancelado_em.isoformat() if self.cancelado_em else None,
            "motivo_cancelamento": self.motivo_cancelamento,
            "cancelado_por_id": self.cancelado_por_id,
            "data_envase": self.data_envase.isoformat() if self.data_envase else None,
            "tipo_envase": self.tipo_envase,
            "status": self.status,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Envase lote_id={self.lote_id} status={self.status}>"
