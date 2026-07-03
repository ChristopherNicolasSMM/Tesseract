"""
addons/addon_brewstation/features/feature_envase/model/item_envase.py

Linha de material de embalagem usado num Envase. `material_id` e
referencia fraca (SEM FK - addon_estoque, skill 02, cross-Addon).

Nome curto "item_envase", nao so "item" - skill 02 lista "item" entre
os nomes genericos de risco de colisao dentro do mesmo Addon.
"""
from core.db import db
from annotations import label, plural, required, min_value


@label("Item de Envase")
@plural("item_envases")
@required("envase_id", message="Envase é obrigatório")
@required("material_id", message="Material é obrigatório")
@min_value("quantidade", 0, message="Quantidade não pode ser negativa")
class ItemEnvase(db.Model):
    __tablename__ = "item_envase"

    id = db.Column(db.Integer, primary_key=True)

    envase_id = db.Column(db.Integer, db.ForeignKey("envase.id", ondelete="CASCADE"), nullable=False, index=True)
    envase = db.relationship("Envase", backref=db.backref("itens", lazy=True))

    material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK - addon_estoque
    quantidade = db.Column(db.Float, nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "envase_id": self.envase_id,
            "material_id": self.material_id,
            "quantidade": self.quantidade,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<ItemEnvase envase_id={self.envase_id} material_id={self.material_id}>"
