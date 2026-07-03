"""
addons/addon_brewstation/features/feature_mash_control/model/mash_recipe.py

Receita de brassagem - canonica, multi-origem (origem_receita) e
versionada (nome+versao unico, toda edicao salva cria uma nova
versao/linha, imutavel apos criada).

CORRECAO desta rodada: `recipe_data` (JSON) removido - ingredientes
passam a ser normalizados em RecipeIngredient (mesma Feature),
resolvidos contra addon_estoque via ingredient_resolution_service.
`brewfather_recipe_id` (campo simples, uma unica origem possivel)
generalizado para `origem_receita`/`origem_receita_id` (multiplas
origens: BrewFather, BeerSmith, BeerXML, Manual).

`Recipe` (modelo legado/duplicado do BrewStation original) foi
deliberadamente descartado - decisao registrada no BACKLOG.md.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices


ORIGENS_RECEITA = ("Manual", "BrewFather", "BeerSmith", "BeerXML")


@label("Receita de Brassagem")
@plural("mash_recipes")
@choices("origem_receita", label="Origem")
@required("name", message="Nome da receita é obrigatório")
@required("origem_receita", message="Origem da receita é obrigatória")
class MashRecipe(db.Model):
    __tablename__ = "recipe"  # nome curto — CrudGen/ModuleManager aplicam o prefixo
    __table_args__ = (
        db.UniqueConstraint("name", "versao", name="uq_recipe_name_versao"),
    )

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    versao = db.Column(db.Integer, nullable=False, default=1)
    description = db.Column(db.Text, nullable=True)
    equipment_mapping = db.Column(db.Text, nullable=True)

    origem_receita = db.Column(db.String(20), nullable=False, default="Manual")  # Manual, BrewFather, BeerSmith, BeerXML
    origem_receita_id = db.Column(db.String(100), nullable=True)  # id externo, nulo se Manual

    created_by = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "versao": self.versao,
            "description": self.description,
            "equipment_mapping": self.equipment_mapping,
            "origem_receita": self.origem_receita,
            "origem_receita_id": self.origem_receita_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<MashRecipe {self.name} v{self.versao}>"
