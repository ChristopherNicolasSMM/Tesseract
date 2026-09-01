"""
addons/addon_brewstation/features/feature_ingredientes/model/levedura.py

Especificacoes de cervejaria de Levedura (spec de ingrediente pra
calculo de receita) - complementar ao Material generico de
addon_estoque. `material_id` e referencia fraca (SEM FK - cross-Addon,
skill 02).

NAO e o mesmo conceito de YeastStrain (feature_yeast_bank, gestao de
banco de cepas fisicas/viabilidade) - relacao observada, nao
resolvida nesta rodada (ver docs/technical/01-visao-geral.md desta
Feature).
"""
from core.db import db
from annotations import label, plural, required, choices, weak_ref

_MATERIAL_RESOLVER = "addons.addon_estoque.root.services.material_lookup.get_material"


@label("Levedura")
@plural("leveduras")
@choices("floculacao", label="Floculação")
@choices("formato", label="Formato")
@weak_ref("material_id", resolver=_MATERIAL_RESOLVER, options="materials",
          bulk_deactivate_service="addons.addon_estoque.root.services.estoque_service.modificar_materiais_em_massa")
@required("material_id", message="Material é obrigatório")
class Levedura(db.Model):
    __tablename__ = "levedura"

    id = db.Column(db.Integer, primary_key=True)

    material_id = db.Column(db.Integer, nullable=False, unique=True, index=True)  # SEM FK - addon_estoque

    atenuacao = db.Column(db.Float, nullable=True)
    temp_fermentacao = db.Column(db.Float, nullable=True)
    floculacao = db.Column(db.String(20), nullable=True)  # baixa, media, alta
    formato = db.Column(db.String(20), nullable=True)  # liquida, seca

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "atenuacao": self.atenuacao,
            "temp_fermentacao": self.temp_fermentacao,
            "floculacao": self.floculacao,
            "formato": self.formato,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<Levedura material_id={self.material_id}>"
