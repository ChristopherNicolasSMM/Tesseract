"""
addons/addon_estoque/root/model/origem.py

Lookup simples (nacional/importado/etc.) - decisão desta sessão
(ampliação de Material, item 1 do escopo). Obrigatório em Material,
mas o autocreate do BrewFather (feature_brew_father) não tem essa
informação disponível na API de origem - resolve para o registro
seed `SEED_NOME_A_DEFINIR` (ver
addons/addon_estoque/root/services/estoque_seed.py), nunca None.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, display_field

SEED_NOME_A_DEFINIR = "A definir"


@display_field("nome")
@label("Origem")
@plural("origems")
@required("nome", message="Nome da origem é obrigatório")
@max_length("nome", 100)
class Origem(db.Model):
    __tablename__ = "origem"

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
        return f"<Origem {self.nome}>"
