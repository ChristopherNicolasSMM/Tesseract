"""
addons/addon_brewstation/features/feature_mash_control/model/recipe_step.py

Timeline única de uma receita — substitui MashStep (decisão
confirmada em conversa: Fermentação fica de fora, é processo separado
que não usa caldeira; Mostura + Fervura + Alerta viram uma tabela só).

`step_type` distingue: "mash" (mostura), "boil" (fervura, não tinha
lugar nenhum antes desta conversa) e "alert" (equivalente ao
`hop_alarms` do tesseract-device-bridge — "dispara X min antes do fim
da etapa-pai"). Diferente de BrewSessionStep (passo EXECUTADO numa
sessão real, copiado/snapshot deste na hora de gerar a sessão) — este
é o planejado na receita.

FK real pra recipe.id e pra si mesma (parent_step_id) — mesma
Feature, skill 02.
"""
from core.db import db
from annotations import label, plural, required, choices, min_value


@label("Etapa da Receita")
@plural("recipe_steps")
@choices("step_type", label="Tipo de Etapa")
@choices("tipo", label="Subtipo (mostura)")
@choices("source", label="Origem")
@required("recipe_id", message="Receita é obrigatória")
class RecipeStep(db.Model):
    __tablename__ = "recipe_step"

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship("MashRecipe", backref=db.backref(
        "recipe_steps", lazy=True, order_by="RecipeStep.ordem", cascade="all, delete-orphan",
    ))

    step_type = db.Column(db.String(20), nullable=False, default="mash")  # mash, boil, alert
    ordem = db.Column(db.Integer, nullable=False, default=0)
    nome = db.Column(db.String(150), nullable=True)

    # Só relevante pra step_type=mash/boil.
    temperatura = db.Column(db.Float, nullable=True)
    tempo_min = db.Column(db.Integer, nullable=True)
    ramp_time_min = db.Column(db.Integer, nullable=True)  # só mash
    tipo = db.Column(db.String(20), nullable=True, default="temperature")  # temperature, infusion, decoction (só mash)

    # Só relevante pra step_type=alert — equivalente a hop_alarms do bridge.
    trigger_minutes_remaining = db.Column(db.Integer, nullable=True)
    parent_step_id = db.Column(db.Integer, db.ForeignKey("recipe_step.id", ondelete="CASCADE"), nullable=True)
    parent_step = db.relationship("RecipeStep", remote_side=[id], backref=db.backref("alert_children", lazy=True))

    # Rastreia se foi digitado à mão ou auto-derivado de um RecipeIngredient
    # (lupulagem — decisão confirmada em conversa: "toda lupulagem cria
    # alertas", sem precisar digitar na mão). Re-sincronização (skill
    # services/recipe_timeline_service.py) usa source_recipe_ingredient_id
    # pra saber qual alerta já existe e não duplicar.
    source = db.Column(db.String(20), nullable=False, default="manual")  # manual, auto_hop
    source_recipe_ingredient_id = db.Column(db.Integer, db.ForeignKey("recipe_ingredient.id", ondelete="CASCADE"), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "step_type": self.step_type,
            "ordem": self.ordem,
            "nome": self.nome,
            "temperatura": self.temperatura,
            "tempo_min": self.tempo_min,
            "ramp_time_min": self.ramp_time_min,
            "tipo": self.tipo,
            "trigger_minutes_remaining": self.trigger_minutes_remaining,
            "parent_step_id": self.parent_step_id,
            "source": self.source,
            "source_recipe_ingredient_id": self.source_recipe_ingredient_id,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        if self.step_type == "alert":
            return f"<RecipeStep alert '{self.nome}' -{self.trigger_minutes_remaining}min>"
        return f"<RecipeStep {self.step_type} '{self.nome}' {self.temperatura}°C {self.tempo_min}min>"
