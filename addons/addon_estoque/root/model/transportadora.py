"""
addons/addon_estoque/root/model/transportadora.py

Fase 3 (skill 23) — cadastro de transportadoras. Mesmo raciocínio de
escopo do Fornecedor (ver model/fornecedor.py) - dentro do próprio
addon_estoque.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, enum_field, display_field


@display_field("nome")
@label("Transportadora")
@plural("transportadoras")
@required("nome", message="Nome é obrigatório")
@required("tipo_frete", message="Tipo de frete é obrigatório")
@max_length("nome", 200)
@max_length("documento", 20)
@max_length("contato_nome", 150)
@max_length("telefone", 30)
@max_length("email", 150)
@enum_field("tipo_frete", options=[
    ("proprio", "Próprio"), ("terceirizado", "Terceirizado"),
])
class Transportadora(db.Model):
    __tablename__ = "transportadora"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(200), nullable=False)
    documento = db.Column(db.String(20), nullable=True)  # CNPJ/CPF
    contato_nome = db.Column(db.String(150), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    tipo_frete = db.Column(db.String(20), nullable=False, default="terceirizado")
    observacoes = db.Column(db.Text, nullable=True)

    ativo = db.Column(db.Boolean, default=True, nullable=False)

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
            "documento": self.documento,
            "contato_nome": self.contato_nome,
            "telefone": self.telefone,
            "email": self.email,
            "tipo_frete": self.tipo_frete,
            "observacoes": self.observacoes,
            "ativo": self.ativo,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Transportadora {self.nome}>"
