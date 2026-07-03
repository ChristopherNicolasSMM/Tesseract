"""
addons/addon_brewstation/features/feature_mash_control/model/recipe_ingredient.py

Linha de ingrediente de uma MashRecipe (mesma Feature, FK real - skill
02). `material_id` e referencia fraca (SEM FK) para
addon_estoque.Material - cross-Addon nunca e FK direta (skill 02).

`descricao_origem` mantido mesmo apos resolvido - e o texto bruto
recebido na importacao (API/arquivo), usado como chave de cache em
IngredientMapping e util para auditoria (o que o usuario efetivamente
digitou/recebeu, mesmo que o Material vinculado tenha outro nome).
"""
from core.db import db
from annotations import label, plural, required, choices, min_value


@label("Ingrediente de Receita")
@plural("recipe_ingredients")
@choices("etapa", label="Etapa")
@choices("status_resolucao", label="Status")
@required("recipe_id", message="Receita é obrigatória")
@min_value("quantidade", 0, message="Quantidade não pode ser negativa")
class RecipeIngredient(db.Model):
    __tablename__ = "recipe_ingredient"

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship("MashRecipe", backref=db.backref("ingredientes", lazy=True))

    material_id = db.Column(db.Integer, nullable=True, index=True)  # SEM FK - addon_estoque, referência fraca

    descricao_origem = db.Column(db.String(300), nullable=False)
    quantidade = db.Column(db.Float, nullable=True)
    unidade_medida = db.Column(db.String(20), nullable=True)
    tempo_adicao_min = db.Column(db.Integer, nullable=True)
    etapa = db.Column(db.String(20), nullable=True, default="fervura")  # mostura, fervura, fermentacao

    status_resolucao = db.Column(db.String(20), nullable=False, default="pendente_depara")  # resolvido, pendente_depara

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "material_id": self.material_id,
            "descricao_origem": self.descricao_origem,
            "quantidade": self.quantidade,
            "unidade_medida": self.unidade_medida,
            "tempo_adicao_min": self.tempo_adicao_min,
            "etapa": self.etapa,
            "status_resolucao": self.status_resolucao,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<RecipeIngredient recipe_id={self.recipe_id} {self.descricao_origem!r}>"
