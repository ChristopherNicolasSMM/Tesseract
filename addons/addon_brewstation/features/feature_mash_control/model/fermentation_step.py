"""
addons/addon_brewstation/features/feature_mash_control/model/fermentation_step.py

Etapa de fermentacao planejada numa receita (temperatura, duracao).
FK real para recipe.id (mesma Feature, skill 02).
"""
from core.db import db
from annotations import label, plural, required, min_value


@label("Etapa de Fermentação")
@plural("fermentation_steps")
@required("recipe_id", message="Receita é obrigatória")
@min_value("temperatura", -5, message="Temperatura muito baixa")
class FermentationStep(db.Model):
    __tablename__ = "fermentation_step"

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship(
        "MashRecipe",
        backref=db.backref("fermentation_steps", lazy=True, order_by="FermentationStep.ordem"),
    )

    nome = db.Column(db.String(100), nullable=True)
    temperatura = db.Column(db.Float, nullable=True)
    tempo_dias = db.Column(db.Float, nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "nome": self.nome,
            "temperatura": self.temperatura,
            "tempo_dias": self.tempo_dias,
            "ordem": self.ordem,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<FermentationStep recipe_id={self.recipe_id} {self.temperatura}°C {self.tempo_dias}d>"
