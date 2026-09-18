"""
addons/addon_brewstation/features/feature_ingredientes/services/preco_padrao_lookup.py

Ponto de acesso público e estável — usado por feature_envase quando
não existe preço real pago (ItemPedidoCompra) pro Material de uma
receita. Mesmo papel de material_lookup.py em addon_estoque: outro
Addon/Feature nunca acessa PrecoPadraoInsumo via ORM direto.
"""
from __future__ import annotations

from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import (
    PrecoPadraoInsumo,
)


def get_valor_padrao(tipo_insumo: str) -> float:
    """Valor padrão (R$) do tipo de insumo — 0.0 se não configurado."""
    row = PrecoPadraoInsumo.query.filter_by(tipo_insumo=tipo_insumo).first()
    return row.valor_padrao if row else 0.0


def listar() -> list[dict]:
    return [p.to_dict() for p in PrecoPadraoInsumo.query.order_by(PrecoPadraoInsumo.tipo_insumo).all()]
