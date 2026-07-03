"""
addons/addon_estoque/root/model/composicao.py

Auto-relacionamento (BOM/kit): um Material pode ser composto por N
outros Materiais (ex.: uma caixa composta de garrafas). FK real -
mesmo Addon, mesma tabela em ambos os lados (skill 02 permite).

CORRECAO: ganhou is_deleted/deleted_at seguindo a skill 02 ("padrao
para qualquer entidade gerada pelo CrudGen") - a omissao original
quebrava a tela de listagem gerada (CrudGen filtra por is_deleted
incondicionalmente).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, min_value


@label("Composição de Material")
@plural("composicaos")
@required("material_pai_id", message="Material pai é obrigatório")
@required("material_componente_id", message="Material componente é obrigatório")
@min_value("quantidade", 0, message="Quantidade não pode ser negativa")
class Composicao(db.Model):
    __tablename__ = "composicao"

    id = db.Column(db.Integer, primary_key=True)

    material_pai_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="CASCADE"), nullable=False, index=True)
    material_pai = db.relationship(
        "Material", foreign_keys=[material_pai_id],
        backref=db.backref("componentes", lazy=True),
    )

    material_componente_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_componente = db.relationship(
        "Material", foreign_keys=[material_componente_id],
        backref=db.backref("usado_em_composicoes", lazy=True),
    )

    quantidade = db.Column(db.Float, nullable=False, default=1.0)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_pai_id": self.material_pai_id,
            "material_componente_id": self.material_componente_id,
            "quantidade": self.quantidade,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Composicao pai={self.material_pai_id} componente={self.material_componente_id}>"
