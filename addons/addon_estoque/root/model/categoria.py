"""
addons/addon_estoque/root/model/categoria.py

Lookup simples - decisão desta sessão (ampliação de Material, item 1
do escopo). SUBSTITUI o campo Material.categoria (string livre) por
FK - a distinção materia_prima/embalagem/kit/outro que existia antes
vira dado de tabela em vez de valor fixo em código, mesmo padrão de
Fabricante/Origem/TipoProduto.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Categoria")
@plural("categorias")
@required("nome", message="Nome da categoria é obrigatório")
@max_length("nome", 100)
class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), unique=True, nullable=False)

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
            "nome": self.nome,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Categoria {self.nome}>"
