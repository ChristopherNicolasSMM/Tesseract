"""
addons/addon_brewstation/features/feature_ingredientes/model/malte.py

Especificacoes de cervejaria de Malte - complementar ao Material
generico de addon_estoque. `material_id` e referencia fraca (SEM FK -
cross-Addon, skill 02), resolvida via
addon_estoque.root.services.material_lookup.
"""
from core.db import db
from annotations import label, plural, required, choices, min_value, weak_ref

_MATERIAL_RESOLVER = "addons.addon_estoque.root.services.material_lookup.get_material"


@label("Malte")
@plural("maltes")
@choices("tipo", label="Tipo")
@weak_ref("material_id", resolver=_MATERIAL_RESOLVER, options="materials",
          bulk_deactivate_service="addons.addon_estoque.root.services.estoque_service.modificar_materiais_em_massa")
@required("material_id", message="Material é obrigatório")
@min_value("cor_ebc", 0, message="Cor EBC não pode ser negativa")
class Malte(db.Model):
    __tablename__ = "malte"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, nullable=False, unique=True, index=True)  # SEM FK - addon_estoque

    cor_ebc = db.Column(db.Float, nullable=True)
    poder_diastatico = db.Column(db.Float, nullable=True)
    rendimento = db.Column(db.Float, nullable=True)
    tipo = db.Column(db.String(30), nullable=True)  # base, especial, torrado, ...

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "cor_ebc": self.cor_ebc,
            "poder_diastatico": self.poder_diastatico,
            "rendimento": self.rendimento,
            "tipo": self.tipo,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<Malte material_id={self.material_id}>"
