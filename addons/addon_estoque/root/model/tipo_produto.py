"""
addons/addon_estoque/root/model/tipo_produto.py

Lookup simples (classificação de Material) - decisão desta sessão
(ampliação de Material, item 1 do escopo). Obrigatório em Material.
O autocreate do BrewFather (feature_brew_father) resolve sempre para
o registro seed `SEED_NOME_INSUMO` (ver
addons/addon_estoque/root/services/estoque_seed.py) - diferente de
Origem, aqui não é um "desconhecido" temporário: tudo que vem do
sync de receita É insumo, de fato, não um placeholder.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


SEED_NOME_INSUMO = "Insumo"

@label("Tipo de Produto")
@plural("tipo_produtos")
@required("descricao", message="Descricao do tipo de produto é obrigatório")
@max_length("descricao", 100)
class TipoProduto(db.Model):
    __tablename__ = "tipo_produto"

    id = db.Column(db.Integer, primary_key=True)

    descricao = db.Column(db.String(100), unique=True, nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)

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
            "descricao": self.descricao,
            "codigo": self.codigo,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<TipoProduto {self.descricao}>"
