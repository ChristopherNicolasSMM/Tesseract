"""
addons/addon_brewstation/features/feature_ingredientes/model/lupulo.py

Especificacoes de cervejaria de Lupulo - complementar ao Material
generico de addon_estoque. `material_id` e referencia fraca (SEM FK -
cross-Addon, skill 02).
"""
from core.db import db
from annotations import label, plural, required, choices, min_value, weak_ref

_MATERIAL_RESOLVER = "addons.addon_estoque.root.services.material_lookup.get_material"


@label("Lúpulo")
@plural("lupulos")
@choices("formato", label="Formato")
@weak_ref("material_id", resolver=_MATERIAL_RESOLVER, options="materials")
@required("material_id", message="Material é obrigatório")
@min_value("alpha_acidos", 0, message="Alfa ácidos não pode ser negativo")
class Lupulo(db.Model):
    __tablename__ = "lupulo"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, nullable=False, unique=True, index=True)  # SEM FK - addon_estoque

    alpha_acidos = db.Column(db.Float, nullable=True)
    beta_acidos = db.Column(db.Float, nullable=True)
    formato = db.Column(db.String(20), nullable=True)  # pellet, folha, plug
    origem = db.Column(db.String(60), nullable=True)
    aroma = db.Column(db.Text, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "alpha_acidos": self.alpha_acidos,
            "beta_acidos": self.beta_acidos,
            "formato": self.formato,
            "origem": self.origem,
            "aroma": self.aroma,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<Lupulo material_id={self.material_id}>"
