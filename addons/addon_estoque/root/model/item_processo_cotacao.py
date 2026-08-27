"""
addons/addon_estoque/root/model/item_processo_cotacao.py

Correção de arquitetura (achado do Christopher, sessão pós-Fase 6.3):
o item pedido (Material + quantidade desejada) vive UMA VEZ no
ProcessoCotacao, não repetido em cada Cotacao/fornecedor. Cada
fornecedor só responde com preço (ItemCotacao.preco_unitario) pra um
ItemProcessoCotacao já existente — nunca digita o Material de novo.

Isso substitui o desenho original da Fase 6.1, onde ItemCotacao tinha
material_id/material_unidade_id/quantidade próprios, redundantes entre
Cotacoes do mesmo processo (e frágeis pra comparação, que agrupava por
nome de Material em vez de uma FK garantida).
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, field_labels, weak_ref


@label("Item do Processo de Cotação")
@plural("item_processo_cotacaos")
@required("processo_cotacao_id", message="Processo de cotação é obrigatório")
@required("material_id", message="Material é obrigatório")
@required("material_unidade_id", message="Unidade é obrigatória")
@required("quantidade_desejada", message="Quantidade desejada é obrigatória")
@weak_ref("material_id",
          resolver="addons.addon_estoque.root.services.material_lookup.get_material",
          options="materials")
@weak_ref("material_unidade_id",
          resolver="addons.addon_estoque.root.services.material_unidade_lookup.get_material_unidade",
          options="material_unidades")
@field_labels({
    "processo_cotacao_id": "Processo de Cotação",
    "material_id": "Material",
    "material_unidade_id": "Unidade",
    "quantidade_desejada": "Quantidade Desejada",
    "observacoes": "Observações",
})
class ItemProcessoCotacao(db.Model):
    __tablename__ = "item_processo_cotacao"

    id = db.Column(db.Integer, primary_key=True)

    processo_cotacao_id = db.Column(db.Integer, db.ForeignKey("processo_cotacao.id", ondelete="CASCADE"), nullable=False, index=True)
    processo_cotacao = db.relationship("ProcessoCotacao", backref=db.backref("itens_pedidos", lazy=True))

    material_id = db.Column(db.Integer, db.ForeignKey("material.id", ondelete="RESTRICT"), nullable=False, index=True)
    material = db.relationship("Material")

    material_unidade_id = db.Column(db.Integer, db.ForeignKey("material_unidade.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_unidade = db.relationship("MaterialUnidade")

    quantidade_desejada = db.Column(db.Float, nullable=False)
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
            "material_id": self.material_id,
            "material_unidade_id": self.material_unidade_id,
            "quantidade_desejada": self.quantidade_desejada,
            "observacoes": self.observacoes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ItemProcessoCotacao processo_cotacao_id={self.processo_cotacao_id} material_id={self.material_id}>"
