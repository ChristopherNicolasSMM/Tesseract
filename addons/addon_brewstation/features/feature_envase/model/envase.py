"""
addons/addon_brewstation/features/feature_envase/model/envase.py

Evento de empacotamento de um Lote (BrewSession, feature_mash_control).
`lote_id` e FK real (mesmo Addon, cross-Feature - skill 02 permite).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices, min_value, enum_field


@label("Envase")
@plural("envases")
@enum_field("status", options=["registrado", "cancelado"])
@choices("status", label="Status")
@required("lote_id", message="Lote é obrigatório")
@min_value("quantidade_litros", 0, message="Quantidade não pode ser negativa")
class Envase(db.Model):
    __tablename__ = "envase"

    id = db.Column(db.Integer, primary_key=True)

    lote_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=False, index=True)
    lote = db.relationship("BrewSession", backref=db.backref("envases", lazy=True))

    quantidade_litros = db.Column(db.Float, nullable=True)
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
            "quantidade_litros": self.quantidade_litros,
            "data_envase": self.data_envase.isoformat() if self.data_envase else None,
            "tipo_envase": self.tipo_envase,
            "status": self.status,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Envase lote_id={self.lote_id} status={self.status}>"
