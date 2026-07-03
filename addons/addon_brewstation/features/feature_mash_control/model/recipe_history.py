"""
addons/addon_brewstation/features/feature_mash_control/model/recipe_history.py

Snapshot completo (JSON) de uma MashRecipe + seus RecipeIngredient no
momento em que uma nova versao e criada. Nao e log campo-a-campo -
cada linha e uma foto completa, usada para comparar/consultar
versoes. FK real para recipe.id (mesma Feature, skill 02).

JSON aqui nao compete com filtro tipado de SmartList (e arquivo de
auditoria, nao tela de operacao do dia a dia) - diferente do
raciocinio que descartou JSON em addon_estoque.Material.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required


@label("Histórico de Receita")
@plural("recipe_historys")
@required("recipe_id", message="Receita é obrigatória")
class RecipeHistory(db.Model):
    __tablename__ = "recipe_history"

    id = db.Column(db.Integer, primary_key=True)

    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe = db.relationship("MashRecipe", backref=db.backref("historico", lazy=True))

    snapshot_data = db.Column(db.Text, nullable=False)  # JSON serializado
    alterado_por = db.Column(db.Integer, db.ForeignKey("tesseract_user.id"), nullable=True)
    alterado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    observacao = db.Column(db.Text, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def get_snapshot(self) -> dict:
        import json
        if not self.snapshot_data:
            return {}
        try:
            return json.loads(self.snapshot_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_snapshot(self, snapshot_dict: dict) -> None:
        import json
        self.snapshot_data = json.dumps(snapshot_dict, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "snapshot_data": self.get_snapshot(),
            "alterado_por": self.alterado_por,
            "alterado_em": self.alterado_em.isoformat() if self.alterado_em else None,
            "observacao": self.observacao,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __repr__(self) -> str:
        return f"<RecipeHistory recipe_id={self.recipe_id} em={self.alterado_em}>"
