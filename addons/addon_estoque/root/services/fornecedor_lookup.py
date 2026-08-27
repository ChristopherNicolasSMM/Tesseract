"""
addons/addon_estoque/root/services/fornecedor_lookup.py

Ponto de acesso público e estável para resolver um Fornecedor —
mesmo papel de material_lookup.py, existe pra servir de `resolver` do
@weak_ref em PedidoCompra/Cotacao (skill 11).

CORREÇÃO (achado real, sessão pós-Fase 6.3): PedidoCompra/Cotacao
nunca tiveram @weak_ref pra fornecedor_id — o formulário de criação
caía no fallback de <input type="number"> pedindo o id cru, e a tela
de detalhe (aba Parceiros de Negócio) não renderizava nada (a
condição `weak_ref_options.get(field)` sempre falsa). Além disso,
Fornecedor nunca teve @display_field — o que quebrava o combo mesmo
nos lugares onde eu já usava `data-weakref-source="fornecedores"`
hardcoded nas telas desenhadas (Fase 5/6): `/api/options/fornecedores`
rejeita qualquer model sem @display_field com HTTP 400
(api/routes/core/options_routes.py, whitelist implícita). Corrigido
nos dois pontos (este lookup + @display_field no model).

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.fornecedor import Fornecedor


def get_fornecedor(fornecedor_id: int | None) -> dict | None:
    """Resolve um Fornecedor pelo id interno. Retorna dict (nunca ORM)."""
    if not fornecedor_id:
        return None
    obj = Fornecedor.query.filter_by(id=fornecedor_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_attr = getattr(Fornecedor, "_display_field", "id")
    data["display"] = getattr(obj, display_attr, None) or f"Fornecedor #{obj.id}"
    return data


def fornecedor_exists(fornecedor_id: int | None) -> bool:
    if not fornecedor_id:
        return False
    return (
        Fornecedor.query
        .filter_by(id=fornecedor_id, is_deleted=False)
        .with_entities(Fornecedor.id)
        .first()
        is not None
    )
