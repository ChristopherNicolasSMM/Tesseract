"""
addons/addon_brewstation/features/feature_mash_control/model/mash_step.py

Passo de mostura planejado numa receita (temperaturas, tempo, rampa).
Diferente de BrewSessionStep (passo executado numa sessao real) -
este e o planejado na receita, aquele e o executado na sessao.
FK real para recipe.id (mesma Feature, skill 02).
"""
from core.db import db
from annotations import label, plural, required, choices, min_value


@label("Passo de Mostura")
@plural("mash_steps")
@choices("tipo", label="Tipo")
@required("recipe_id", message="Receita é obrigatória")
@required("temperatura", message="Temperatura é obrigatória")
@min_value("temperatura", 0, message="Temperatura não pode ser negativa")
class MashStep(db.Model):
    __tablename__ = "mash_step"

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship("MashRecipe", backref=db.backref("mash_steps", lazy=True, order_by="MashStep.ordem"))

    nome = db.Column(db.String(100), nullable=True)
    temperatura = db.Column(db.Float, nullable=False)
    tempo_min = db.Column(db.Integer, nullable=True)
    ramp_time_min = db.Column(db.Integer, nullable=True)
    tipo = db.Column(db.String(20), nullable=True, default="temperature")  # temperature, infusion, decoction
    ordem = db.Column(db.Integer, nullable=False, default=0)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "nome": self.nome,
            "temperatura": self.temperatura,
            "tempo_min": self.tempo_min,
            "ramp_time_min": self.ramp_time_min,
            "tipo": self.tipo,
            "ordem": self.ordem,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<MashStep recipe_id={self.recipe_id} {self.temperatura}°C {self.tempo_min}min>"
