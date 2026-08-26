"""
addons/addon_estoque/root/model/processo_cotacao.py

Fase 6.1 (skill 24) — cabeçalho do processo de cotação (RFQ), agrupa
N Cotacao (uma por fornecedor convidado) pra comparação. `numero` é
gerado automaticamente (COT-000001) via hook, mesmo padrão de
PedidoCompra.numero (skill 23, Fase 4).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels


@label("Processo de Cotação")
@plural("processo_cotacaos")
@required("descricao", message="Descrição é obrigatória")
@required("data_abertura", message="Data de abertura é obrigatória")
@enum_field("status", options=[
    ("aberto", "Aberto"), ("comparado", "Comparado"),
    ("finalizado", "Finalizado"), ("cancelado", "Cancelado"),
])
@field_labels({
    "numero": "Número",
    "descricao": "Descrição",
    "status": "Status",
    "data_abertura": "Data de Abertura",
    "data_limite_resposta": "Prazo para Resposta",
})
class ProcessoCotacao(db.Model):
    __tablename__ = "processo_cotacao"

    id = db.Column(db.Integer, primary_key=True)

    numero = db.Column(db.String(30), unique=True, nullable=True)  # preenchido no hook se ausente

    descricao = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="aberto")
    data_abertura = db.Column(db.Date, nullable=False)
    data_limite_resposta = db.Column(db.Date, nullable=True)
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
            "numero": self.numero,
            "descricao": self.descricao,
            "status": self.status,
            "data_abertura": self.data_abertura.isoformat() if self.data_abertura else None,
            "data_limite_resposta": self.data_limite_resposta.isoformat() if self.data_limite_resposta else None,
            "observacoes": self.observacoes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ProcessoCotacao {self.numero} status={self.status}>"
