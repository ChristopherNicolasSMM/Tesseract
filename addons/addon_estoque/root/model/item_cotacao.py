"""
addons/addon_estoque/root/model/item_cotacao.py

Fase 6.1 (skill 24) — linha de uma Cotacao (Material pedido a um
fornecedor específico dentro do processo). Mesmo padrão de
ItemPedidoCompra (skill 23, Fase 4): fator_conversao_aplicado/
quantidade_convertida_base/subtotal calculados no hook, nunca aceitos
do payload (readonly).

`selecionado_como_vencedor`: setado pela tela de Comparação (Fase
6.2, ainda não implementada), nunca editado direto pelo formulário
genérico do CrudGen — regra de "um vencedor por Material no processo"
atravessa Cotacao (fornecedores diferentes), não é validável por
constraint de banco, fica pra o service da Fase 6.2 aplicar.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, readonly_fields, field_labels


@label("Item da Cotação")
@plural("item_cotacaos")
@required("cotacao_id", message="Cotação é obrigatória")
@required("material_id", message="Material é obrigatório")
@required("material_unidade_id", message="Unidade de compra é obrigatória")
@required("quantidade", message="Quantidade é obrigatória")
@required("preco_unitario", message="Preço unitário é obrigatório")
@readonly_fields(["fator_conversao_aplicado", "quantidade_convertida_base", "subtotal"])
@field_labels({
    "cotacao_id": "Cotação",
    "material_id": "Material",
    "material_unidade_id": "Unidade de Compra",
    "quantidade": "Quantidade",
    "fator_conversao_aplicado": "Fator de Conversão Aplicado",
    "quantidade_convertida_base": "Quantidade (Unidade-Base)",
    "preco_unitario": "Preço Unitário",
    "subtotal": "Subtotal",
    "selecionado_como_vencedor": "Selecionado como Vencedor",
})
class ItemCotacao(db.Model):
    __tablename__ = "item_cotacao"

    id = db.Column(db.Integer, primary_key=True)

    cotacao_id = db.Column(db.Integer, db.ForeignKey("cotacao.id", ondelete="CASCADE"), nullable=False, index=True)
    cotacao = db.relationship("Cotacao", backref=db.backref("itens", lazy=True))

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False, index=True)
    material = db.relationship("Material")

    material_unidade_id = db.Column(db.Integer, db.ForeignKey("material_unidade.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_unidade = db.relationship("MaterialUnidade")

    quantidade = db.Column(db.Float, nullable=False)
    fator_conversao_aplicado = db.Column(db.Float, nullable=True)
    quantidade_convertida_base = db.Column(db.Float, nullable=True)

    preco_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=True)

    selecionado_como_vencedor = db.Column(db.Boolean, default=False, nullable=False)

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
            "cotacao_id": self.cotacao_id,
            "material_id": self.material_id,
            "material_unidade_id": self.material_unidade_id,
            "quantidade": self.quantidade,
            "fator_conversao_aplicado": self.fator_conversao_aplicado,
            "quantidade_convertida_base": self.quantidade_convertida_base,
            "preco_unitario": self.preco_unitario,
            "subtotal": self.subtotal,
            "selecionado_como_vencedor": self.selecionado_como_vencedor,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ItemCotacao cotacao_id={self.cotacao_id} material_id={self.material_id}>"
