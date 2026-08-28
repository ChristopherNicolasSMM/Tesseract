"""
addons/addon_estoque/root/services/tipo_produto_lookup.py

Ponto de acesso público e estável para resolver um TipoProduto —
mesmo papel/mesma correção de fornecedor_lookup.py. Usado como
resolver do @weak_ref em Material.tipo_produto_id e
Categoria.tipo_produto_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.tipo_produto import TipoProduto


def get_tipo_produto(tipo_produto_id: int | None) -> dict | None:
    """Resolve um TipoProduto pelo id interno. Retorna dict (nunca ORM)."""
    if not tipo_produto_id:
        return None
    obj = TipoProduto.query.filter_by(id=tipo_produto_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    data["display"] = obj.descricao or f"Tipo de Produto #{obj.id}"
    return data
