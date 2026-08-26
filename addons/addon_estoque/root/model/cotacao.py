"""
addons/addon_estoque/root/model/cotacao.py

Fase 6.1 (skill 24) — um cabeçalho POR fornecedor convidado dentro de
um ProcessoCotacao (RFQ). `numero` gerado automaticamente no hook,
formato "{numero_do_processo}-{sufixo_letra}" (ver skill 24, seção 4).

Índice único parcial: no máximo uma Cotacao não-deletada por
(processo_cotacao_id, fornecedor_id) - não faz sentido convidar o
mesmo fornecedor duas vezes no mesmo processo.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels


@label("Cotação")
@plural("cotacaos")
@required("processo_cotacao_id", message="Processo de cotação é obrigatório")
@required("fornecedor_id", message="Fornecedor é obrigatório")
@enum_field("status", options=[
    ("rascunho", "Rascunho"), ("enviada", "Enviada"),
    ("respondida", "Respondida"), ("recusada", "Recusada"),
])
@field_labels({
    "processo_cotacao_id": "Processo de Cotação",
    "fornecedor_id": "Fornecedor",
    "numero": "Número",
    "status": "Status",
    "condicao_pagamento": "Condição de Pagamento",
    "prazo_entrega_dias": "Prazo de Entrega (dias)",
})
class Cotacao(db.Model):
    __tablename__ = "cotacao"

    __table_args__ = (
        db.Index(
            "uq_cotacao_processo_fornecedor", "processo_cotacao_id", "fornecedor_id",
            unique=True, sqlite_where=db.text("is_deleted = 0"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    processo_cotacao_id = db.Column(db.Integer, db.ForeignKey("processo_cotacao.id", ondelete="CASCADE"), nullable=False, index=True)
    processo_cotacao = db.relationship("ProcessoCotacao", backref=db.backref("cotacoes", lazy=True))

    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedor.id", ondelete="RESTRICT"), nullable=False, index=True)
    fornecedor = db.relationship("Fornecedor")

    numero = db.Column(db.String(40), unique=True, nullable=True)  # preenchido no hook se ausente

    status = db.Column(db.String(20), nullable=False, default="rascunho")
    condicao_pagamento = db.Column(db.String(100), nullable=True)
    prazo_entrega_dias = db.Column(db.Integer, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

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
            "processo_cotacao_id": self.processo_cotacao_id,
            "fornecedor_id": self.fornecedor_id,
            "numero": self.numero,
            "status": self.status,
            "condicao_pagamento": self.condicao_pagamento,
            "prazo_entrega_dias": self.prazo_entrega_dias,
            "observacoes": self.observacoes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Cotacao {self.numero} fornecedor_id={self.fornecedor_id} status={self.status}>"
