"""
addons/addon_estoque/root/services/origem_lookup.py

Ponto de acesso público e estável para resolver uma Origem — mesmo
papel/mesma correção de fornecedor_lookup.py. Usado como resolver do
@weak_ref em Material.origem_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.origem import Origem


def get_origem(origem_id: int | None) -> dict | None:
    """Resolve uma Origem pelo id interno. Retorna dict (nunca ORM)."""
    if not origem_id:
        return None
    obj = Origem.query.filter_by(id=origem_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    data["display"] = obj.nome or f"Origem #{obj.id}"
    return data
