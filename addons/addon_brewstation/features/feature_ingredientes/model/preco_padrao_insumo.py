"""
addons/addon_brewstation/features/feature_ingredientes/model/preco_padrao_insumo.py

Preço padrão por TIPO de insumo (malte / lúpulo / levedura) — não por
Material individual, nem genérico pra qualquer Categoria/TipoProduto
de addon_estoque. É específico do domínio BrewStation (decisão da
conversa, proposta-precificacao-envase.md §6.1): quando
feature_envase não encontra um preço real pago (ItemPedidoCompra) pra
um Material usado numa receita, cai neste valor padrão, escolhido
pelo tipo de insumo ao qual o Material pertence (Malte, Lupulo ou
Levedura, feature_ingredientes).

3 linhas hoje (uma por tipo já existente como model próprio nesta
Feature); extensível se aparecer um 4º tipo de insumo.
"""
from datetime import datetime, timezone

from core.db import db
from annotations import label, plural, required, choices, enum_field, min_value, field_labels

TIPOS_INSUMO = ("malte", "lupulo", "levedura")


@label("Preço Padrão de Insumo")
@plural("preco_padrao_insumos")
@enum_field("tipo_insumo", options=list(TIPOS_INSUMO))
@choices("tipo_insumo", label="Tipo de Insumo")
@required("tipo_insumo", message="Tipo de insumo é obrigatório")
@required("valor_padrao", message="Valor padrão é obrigatório")
@min_value("valor_padrao", 0, message="Valor padrão não pode ser negativo")
@field_labels({
    "tipo_insumo": "Tipo de Insumo",
    "valor_padrao": "Valor Padrão",
    "unidade": "Unidade",
})
class PrecoPadraoInsumo(db.Model):
    __tablename__ = "preco_padrao_insumo"
    __table_args__ = (
        db.UniqueConstraint("tipo_insumo", name="uq_preco_padrao_insumo_tipo"),
    )

    id = db.Column(db.Integer, primary_key=True)

    tipo_insumo = db.Column(db.String(20), nullable=False)  # malte, lupulo, levedura
    valor_padrao = db.Column(db.Float, nullable=False, default=0.0)
    unidade = db.Column(db.String(10), nullable=False, default="kg")  # kg, un, ...

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo_insumo": self.tipo_insumo,
            "valor_padrao": self.valor_padrao,
            "unidade": self.unidade,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<PrecoPadraoInsumo {self.tipo_insumo}={self.valor_padrao}/{self.unidade}>"
