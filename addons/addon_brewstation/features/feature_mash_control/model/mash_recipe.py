"""
addons/addon_brewstation/features/feature_mash_control/model/mash_recipe.py

Receita de brassagem — armazena os dados da receita como JSON em
`recipe_data` (igual ao original). `Recipe` (modelo legado/duplicado
do BrewStation original) foi deliberadamente descartado — decisão
registrada no BACKLOG.md.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Receita de Brassagem")
@plural("mash_recipes")
@required("name", message="Nome da receita é obrigatório")
class MashRecipe(db.Model):
    __tablename__ = "recipe"  # nome curto — CrudGen/ModuleManager aplicam o prefixo

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    recipe_data = db.Column(db.Text, nullable=True)  # JSON serializado
    equipment_mapping = db.Column(db.Text, nullable=True)
    brewfather_recipe_id = db.Column(db.String(100), nullable=True)
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

    def get_recipe_data(self) -> dict:
        import json
        if not self.recipe_data:
            return {}
        try:
            return json.loads(self.recipe_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "recipe_data": self.get_recipe_data(),
            "equipment_mapping": self.equipment_mapping,
            "brewfather_recipe_id": self.brewfather_recipe_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<MashRecipe {self.name}>"
