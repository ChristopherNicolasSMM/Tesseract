"""
addons/addon_estoque/root/model/fabricante.py

Lookup simples (fabricante/marca do Material) - decisão desta sessão
(ampliação de Material, item 1 do escopo). `nome` é a chave de
negócio (unique), igual ao padrão já usado em Material.nome.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length


@label("Fabricante")
@plural("fabricantes")
@required("nome", message="Nome do fabricante é obrigatório")
@max_length("nome", 150)
class Fabricante(db.Model):
    __tablename__ = "fabricante"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), unique=True, nullable=False)

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
        return f"<Fabricante {self.nome}>"
