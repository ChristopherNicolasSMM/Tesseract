"""
addons/addon_estoque/root/model/fornecedor.py

Fase 3 (skill 23) — cadastro de fornecedores. Decisão raiz da skill 23:
vive dentro do próprio addon_estoque (não em addon_compras separado) —
FK real permitida com Movimentacao/PedidoCompra (Fase 4, ainda não
implementada) por serem do mesmo Addon.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, max_length, display_field


@display_field("razao_social")
@label("Fornecedor")
@plural("fornecedores")
@required("razao_social", message="Razão social é obrigatória")
@max_length("razao_social", 200)
@max_length("nome_fantasia", 200)
@max_length("documento", 20)
@max_length("contato_nome", 150)
@max_length("telefone", 30)
@max_length("email", 150)
@max_length("condicao_pagamento_padrao", 100)
class Fornecedor(db.Model):
    __tablename__ = "fornecedor"

    id = db.Column(db.Integer, primary_key=True)

    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=True)
    documento = db.Column(db.String(20), nullable=True)  # CNPJ/CPF - livre de propósito (formatos variam)
    contato_nome = db.Column(db.String(150), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    condicao_pagamento_padrao = db.Column(db.String(100), nullable=True)
    prazo_entrega_padrao_dias = db.Column(db.Integer, nullable=True)
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
            "razao_social": self.razao_social,
            "nome_fantasia": self.nome_fantasia,
            "documento": self.documento,
            "contato_nome": self.contato_nome,
            "telefone": self.telefone,
            "email": self.email,
            "condicao_pagamento_padrao": self.condicao_pagamento_padrao,
            "prazo_entrega_padrao_dias": self.prazo_entrega_padrao_dias,
            "observacoes": self.observacoes,
            "ativo": self.ativo,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Fornecedor {self.razao_social}>"
