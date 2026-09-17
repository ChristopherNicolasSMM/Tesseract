"""
addons/addon_estoque/root/services/cotacao_lookup.py

Ponto de acesso público e estável para resolver uma Cotacao pelo
`id` — usado por `@weak_ref` (skill 11) de campos que são FK real
DENTRO do próprio Addon (`ItemCotacao.cotacao_id`). Mesmo papel de
material_lookup.py/fornecedor_lookup.py.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.cotacao import Cotacao


def get_cotacao(cotacao_id: int | None) -> dict | None:
    """Resolve uma Cotacao pelo id interno. Retorna dict (nunca ORM)."""
    if not cotacao_id:
        return None
    obj = Cotacao.query.filter_by(id=cotacao_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(Cotacao, "_display_field", "id")
    data["display"] = getattr(obj, display_field, None) or f"Cotação #{obj.id}"
    return data
