"""
addons/addon_brewstation/features/feature_mash_control/model/ingredient_mapping.py

Cache de resolucao de ingrediente (de-para): uma vez que o usuario
resolve manualmente "descricao X vinda da origem Y" para um Material
especifico, fica gravado aqui - proximas importacoes da mesma
origem+descricao resolvem automatico, sem perguntar de novo.

`material_id` e referencia fraca (SEM FK) para addon_estoque.Material,
mesma regra de RecipeIngredient.
"""
from core.db import db
from annotations import label, plural, required, choices


@label("Mapeamento de Ingrediente")
@plural("ingredient_mappings")
@choices("origem_receita", label="Origem")
@required("origem_receita", message="Origem é obrigatória")
@required("descricao_origem", message="Descrição de origem é obrigatória")
@required("material_id", message="Material é obrigatório")
class IngredientMapping(db.Model):
    __tablename__ = "ingredient_mapping"
    __table_args__ = (
        db.UniqueConstraint("origem_receita", "descricao_origem", name="uq_ingredient_mapping_origem_descricao"),
    )

    id = db.Column(db.Integer, primary_key=True)

    origem_receita = db.Column(db.String(20), nullable=False)  # mesmo domínio de MashRecipe.origem_receita
    descricao_origem = db.Column(db.String(300), nullable=False)
    material_id = db.Column(db.Integer, nullable=False, index=True)  # SEM FK - addon_estoque, referência fraca

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "origem_receita": self.origem_receita,
            "descricao_origem": self.descricao_origem,
            "material_id": self.material_id,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<IngredientMapping {self.origem_receita}:{self.descricao_origem!r} -> material_id={self.material_id}>"
