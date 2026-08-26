"""
addons/addon_estoque/root/model/item_pedido_compra.py

Fase 4 (skill 23) — linha de um PedidoCompra. Esta tabela É o
histórico de preços/últimas compras (não existe tabela separada —
consulta de "últimas compras deste Material" é uma query sobre esta
tabela + PedidoCompra.data_pedido).

`quantidade` é sempre na UNIDADE DE COMPRA (material_unidade_id), não
na unidade-base do Material — `fator_conversao_aplicado` (snapshot de
MaterialUnidade.fator_para_base no momento do save, nunca recalculado
depois — se o fator mudar no cadastro, histórico já gravado não
muda) e `quantidade_convertida_base` (= quantidade * fator) são
calculados no hook (item_pedido_compras_service_hooks.py), assim como
`subtotal` (= quantidade * preco_unitario).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, readonly_fields, field_labels


@label("Item do Pedido de Compra")
@plural("item_pedido_compras")
@required("pedido_compra_id", message="Pedido de compra é obrigatório")
@required("material_id", message="Material é obrigatório")
@required("material_unidade_id", message="Unidade de compra é obrigatória")
@required("quantidade", message="Quantidade é obrigatória")
@required("preco_unitario", message="Preço unitário é obrigatório")
@readonly_fields(["fator_conversao_aplicado", "quantidade_convertida_base", "subtotal"])
@field_labels({
    "pedido_compra_id": "Pedido de Compra",
    "material_id": "Material",
    "material_unidade_id": "Unidade de Compra",
    "quantidade": "Quantidade",
    "fator_conversao_aplicado": "Fator de Conversão Aplicado",
    "quantidade_convertida_base": "Quantidade (Unidade-Base)",
    "preco_unitario": "Preço Unitário",
    "subtotal": "Subtotal",
})
class ItemPedidoCompra(db.Model):
    __tablename__ = "item_pedido_compra"

    id = db.Column(db.Integer, primary_key=True)

    pedido_compra_id = db.Column(db.Integer, db.ForeignKey("pedido_compra.id", ondelete="CASCADE"), nullable=False, index=True)
    pedido_compra = db.relationship("PedidoCompra", backref=db.backref("itens", lazy=True))

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False, index=True)
    material = db.relationship("Material")

    material_unidade_id = db.Column(db.Integer, db.ForeignKey("material_unidade.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_unidade = db.relationship("MaterialUnidade")

    quantidade = db.Column(db.Float, nullable=False)  # na unidade de compra
    fator_conversao_aplicado = db.Column(db.Float, nullable=True)  # snapshot, calculado no hook
    quantidade_convertida_base = db.Column(db.Float, nullable=True)  # calculado no hook

    preco_unitario = db.Column(db.Float, nullable=False)  # por unidade de compra
    subtotal = db.Column(db.Float, nullable=True)  # calculado no hook

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
            "pedido_compra_id": self.pedido_compra_id,
            "material_id": self.material_id,
            "material_unidade_id": self.material_unidade_id,
            "quantidade": self.quantidade,
            "fator_conversao_aplicado": self.fator_conversao_aplicado,
            "quantidade_convertida_base": self.quantidade_convertida_base,
            "preco_unitario": self.preco_unitario,
            "subtotal": self.subtotal,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ItemPedidoCompra pedido_compra_id={self.pedido_compra_id} material_id={self.material_id}>"
