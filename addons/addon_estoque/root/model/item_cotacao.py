"""
addons/addon_estoque/root/model/item_cotacao.py

REESTRUTURADO (achado do Christopher, sessão pós-Fase 6.3): antes,
ItemCotacao carregava material_id/material_unidade_id/quantidade
próprios — redundante entre Cotacoes do mesmo processo (o mesmo
Material digitado de novo pra cada fornecedor) e frágil pra
comparação (agrupava por nome de Material, sem garantia de ser o
mesmo item). Agora ItemCotacao é só a RESPOSTA de preço de um
fornecedor pra um ItemProcessoCotacao já definido uma vez no processo
(ver model/item_processo_cotacao.py) — nunca redigita o Material.

`quantidade_ofertada` é opcional: nulo significa "o fornecedor
confirma a quantidade pedida" (ItemProcessoCotacao.quantidade_desejada);
preenchido significa "só consigo entregar X, diferente do pedido".
fator_conversao_aplicado/quantidade_convertida_base/subtotal usam
sempre a MESMA unidade do ItemProcessoCotacao (skill 24, decisão desta
correção: não permite fornecedor cotar em unidade diferente da
pedida — simplifica a comparação; se isso virar necessidade real,
revisar).

`selecionado_como_vencedor`: setado pela tela de Comparação (Fase
6.2), nunca editado direto pelo formulário genérico do CrudGen — regra
de "um vencedor por item do processo" atravessa Cotacao (fornecedores
diferentes), não é validável por constraint de banco, fica pro service
aplicar (estoque_service.selecionar_item_cotacao_vencedor).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, readonly_fields, field_labels


@label("Item da Cotação")
@plural("item_cotacaos")
@required("cotacao_id", message="Cotação é obrigatória")
@required("item_processo_cotacao_id", message="Item do processo é obrigatório")
@required("preco_unitario", message="Preço unitário é obrigatório")
@readonly_fields(["fator_conversao_aplicado", "quantidade_convertida_base", "subtotal", "pedido_compra_item_id"])
@field_labels({
    "cotacao_id": "Cotação",
    "item_processo_cotacao_id": "Item Pedido",
    "quantidade_ofertada": "Quantidade Ofertada (se diferente da pedida)",
    "fator_conversao_aplicado": "Fator de Conversão Aplicado",
    "quantidade_convertida_base": "Quantidade (Unidade-Base)",
    "preco_unitario": "Preço Unitário",
    "subtotal": "Subtotal",
    "selecionado_como_vencedor": "Selecionado como Vencedor",
    "pedido_compra_item_id": "Item do Pedido Gerado",
})
class ItemCotacao(db.Model):
    __tablename__ = "item_cotacao"

    id = db.Column(db.Integer, primary_key=True)

    cotacao_id = db.Column(db.Integer, db.ForeignKey("cotacao.id", ondelete="CASCADE"), nullable=False, index=True)
    cotacao = db.relationship("Cotacao", backref=db.backref("itens", lazy=True))

    item_processo_cotacao_id = db.Column(db.Integer, db.ForeignKey("item_processo_cotacao.id", ondelete="CASCADE"), nullable=False, index=True)
    item_processo_cotacao = db.relationship("ItemProcessoCotacao", backref=db.backref("respostas", lazy=True))

    quantidade_ofertada = db.Column(db.Float, nullable=True)
    fator_conversao_aplicado = db.Column(db.Float, nullable=True)
    quantidade_convertida_base = db.Column(db.Float, nullable=True)

    preco_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=True)

    selecionado_como_vencedor = db.Column(db.Boolean, default=False, nullable=False)

    # Fase 6.3 (skill 24) - rastreia se este item vencedor já gerou
    # ItemPedidoCompra, evitando duplicar pedido se "Gerar Pedido" for
    # chamado mais de uma vez no mesmo ProcessoCotacao. Também dá
    # rastreabilidade completa (cotação -> pedido), mesmo espírito de
    # Movimentacao.pedido_compra_item_id (skill 23, Fase 4).
    pedido_compra_item_id = db.Column(db.Integer, db.ForeignKey("item_pedido_compra.id", ondelete="SET NULL"), nullable=True)
    pedido_compra_item = db.relationship("ItemPedidoCompra")

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def material_id(self):
        """Atalho de conveniência - lê do ItemProcessoCotacao pai."""
        return self.item_processo_cotacao.material_id if self.item_processo_cotacao else None

    @property
    def material_unidade_id(self):
        return self.item_processo_cotacao.material_unidade_id if self.item_processo_cotacao else None

    @property
    def quantidade(self):
        """Quantidade efetiva: a ofertada, ou a desejada se o
        fornecedor não divergiu."""
        if self.quantidade_ofertada is not None:
            return self.quantidade_ofertada
        return self.item_processo_cotacao.quantidade_desejada if self.item_processo_cotacao else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cotacao_id": self.cotacao_id,
            "item_processo_cotacao_id": self.item_processo_cotacao_id,
            "material_id": self.material_id,
            "material_unidade_id": self.material_unidade_id,
            "quantidade": self.quantidade,
            "quantidade_ofertada": self.quantidade_ofertada,
            "fator_conversao_aplicado": self.fator_conversao_aplicado,
            "quantidade_convertida_base": self.quantidade_convertida_base,
            "preco_unitario": self.preco_unitario,
            "subtotal": self.subtotal,
            "selecionado_como_vencedor": self.selecionado_como_vencedor,
            "pedido_compra_item_id": self.pedido_compra_item_id,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ItemCotacao cotacao_id={self.cotacao_id} item_processo_cotacao_id={self.item_processo_cotacao_id}>"
