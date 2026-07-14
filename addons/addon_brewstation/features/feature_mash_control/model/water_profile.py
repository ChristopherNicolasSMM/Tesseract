"""
addons/addon_brewstation/features/feature_mash_control/model/water_profile.py

Perfil de água de uma receita (item (c) do BACKLOG.md — decidido após
verificação contra a API real do BrewFather). FK real pra recipe.id
(mesma Feature, skill 02) — mesmo padrão de RecipeStep/FermentationStep.

Não passa por ingredient_resolution_service (isso é só pra
ingrediente, que referencia Material) — gravado direto em
sync_service._importar_receita, um registro por contexto disponível
na receita importada.

`contexto` distingue os 5 momentos do cálculo de água que o BrewFather
expõe (Water Calculator): `source` (água de origem, antes de
qualquer ajuste), `target` (perfil-alvo escolhido), `mash` (água de
mostura após ajuste), `sparge` (água de lavagem após ajuste), `total`
(mistura calculada mash+sparge). UniqueConstraint(recipe_id, contexto)
— uma receita tem no máximo um registro por contexto.
"""
from core.db import db
from annotations import label, plural, required, choices

CONTEXTOS_WATER_PROFILE = ("source", "target", "mash", "sparge", "total")


@label("Perfil de Água")
@plural("water_profiles")
@choices("contexto", label="Contexto")
@required("recipe_id", message="Receita é obrigatória")
@required("contexto", message="Contexto é obrigatório")
class WaterProfile(db.Model):
    __tablename__ = "water_profile"
    __table_args__ = (
        db.UniqueConstraint("recipe_id", "contexto", name="uq_water_profile_recipe_contexto"),
    )

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship("MashRecipe", backref=db.backref("water_profiles", lazy=True))

    contexto = db.Column(db.String(10), nullable=False)  # source, target, mash, sparge, total

    calcio = db.Column(db.Float, nullable=True)       # Ca, ppm
    magnesio = db.Column(db.Float, nullable=True)      # Mg, ppm
    sodio = db.Column(db.Float, nullable=True)         # Na, ppm
    cloreto = db.Column(db.Float, nullable=True)       # Cl, ppm
    sulfato = db.Column(db.Float, nullable=True)       # SO4, ppm
    bicarbonato = db.Column(db.Float, nullable=True)   # HCO3, ppm
    ph = db.Column(db.Float, nullable=True)            # 0-14

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "contexto": self.contexto,
            "calcio": self.calcio,
            "magnesio": self.magnesio,
            "sodio": self.sodio,
            "cloreto": self.cloreto,
            "sulfato": self.sulfato,
            "bicarbonato": self.bicarbonato,
            "ph": self.ph,
            "is_deleted": self.is_deleted,
        }

    def __repr__(self) -> str:
        return f"<WaterProfile recipe_id={self.recipe_id} contexto={self.contexto}>"
