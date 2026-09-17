"""
addons/addon_estoque/root/services/pedido_compra_lookup.py

Ponto de acesso público e estável para resolver um PedidoCompra pelo
`id` — usado por `@weak_ref` (skill 11) de campos que são FK real
DENTRO do próprio Addon (`ItemPedidoCompra.pedido_compra_id`). Mesmo
papel de material_lookup.py/fornecedor_lookup.py.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.pedido_compra import PedidoCompra


def get_pedido_compra(pedido_compra_id: int | None) -> dict | None:
    """Resolve um PedidoCompra pelo id interno. Retorna dict (nunca ORM)."""
    if not pedido_compra_id:
        return None
    obj = PedidoCompra.query.filter_by(id=pedido_compra_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(PedidoCompra, "_display_field", "id")
    data["display"] = getattr(obj, display_field, None) or f"Pedido #{obj.id}"
    return data
