"""
addons/addon_estoque/root/model/pedido_compra.py

Fase 4 (skill 23) — cabeçalho do pedido de compra. Fluxo: rascunho ->
enviado -> confirmado -> recebido (ou cancelado a qualquer momento
antes de recebido). Recebimento é SEMPRE total nesta fase (decisão
explícita — recebimento parcial fica para quando o volume real de uso
justificar, skill 23 seção 6) e é feito via
estoque_service.receber_pedido_compra(), nunca setando status="recebido"
direto por fora dele (é isso que dispara a geração das Movimentacao).

`numero` é gerado automaticamente (sequencial, formato PC-000001) no
hook de criação (pedido_compras_service_hooks.py) quando não
informado — editável depois, mesmo padrão que Material.sku documenta
(gerado, mas não travado).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, enum_field, field_labels


@label("Pedido de Compra")
@plural("pedido_compras")
@required("fornecedor_id", message="Fornecedor é obrigatório")
@required("data_pedido", message="Data do pedido é obrigatória")
@enum_field("status", options=[
    ("rascunho", "Rascunho"), ("enviado", "Enviado"),
    ("confirmado", "Confirmado"), ("recebido", "Recebido"),
    ("cancelado", "Cancelado"),
])
@field_labels({
    "numero": "Número",
    "fornecedor_id": "Fornecedor",
    "transportadora_id": "Transportadora",
    "status": "Status",
    "data_pedido": "Data do Pedido",
    "data_previsao_entrega": "Previsão de Entrega",
    "condicao_pagamento": "Condição de Pagamento",
    "valor_frete": "Valor do Frete",
})
class PedidoCompra(db.Model):
    __tablename__ = "pedido_compra"

    id = db.Column(db.Integer, primary_key=True)

    numero = db.Column(db.String(30), unique=True, nullable=True)  # preenchido no hook se ausente

    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedor.id", ondelete="RESTRICT"), nullable=False, index=True)
    fornecedor = db.relationship("Fornecedor")

    transportadora_id = db.Column(db.Integer, db.ForeignKey("transportadora.id", ondelete="RESTRICT"), nullable=True, index=True)
    transportadora = db.relationship("Transportadora")

    status = db.Column(db.String(20), nullable=False, default="rascunho")

    data_pedido = db.Column(db.Date, nullable=False)
    data_previsao_entrega = db.Column(db.Date, nullable=True)
    condicao_pagamento = db.Column(db.String(100), nullable=True)
    valor_frete = db.Column(db.Float, nullable=True)
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
            "fornecedor_id": self.fornecedor_id,
            "transportadora_id": self.transportadora_id,
            "status": self.status,
            "data_pedido": self.data_pedido.isoformat() if self.data_pedido else None,
            "data_previsao_entrega": self.data_previsao_entrega.isoformat() if self.data_previsao_entrega else None,
            "condicao_pagamento": self.condicao_pagamento,
            "valor_frete": self.valor_frete,
            "observacoes": self.observacoes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<PedidoCompra {self.numero} status={self.status}>"
