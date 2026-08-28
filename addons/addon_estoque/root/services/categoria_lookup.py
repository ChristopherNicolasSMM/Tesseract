"""
addons/addon_estoque/root/services/categoria_lookup.py

Ponto de acesso público e estável para resolver uma Categoria — mesmo
papel/mesma correção de fornecedor_lookup.py. Usado como resolver do
@weak_ref em Material.categoria_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.categoria import Categoria


def get_categoria(categoria_id: int | None) -> dict | None:
    """Resolve uma Categoria pelo id interno. Retorna dict (nunca ORM)."""
    if not categoria_id:
        return None
    obj = Categoria.query.filter_by(id=categoria_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    data["display"] = obj.descricao or f"Categoria #{obj.id}"
    return data
