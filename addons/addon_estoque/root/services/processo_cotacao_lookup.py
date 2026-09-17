"""
addons/addon_estoque/root/services/processo_cotacao_lookup.py

Ponto de acesso público e estável para resolver um ProcessoCotacao
pelo `id` — usado por `@weak_ref` (skill 11) de campos que são FK
real DENTRO do próprio Addon (`Cotacao.processo_cotacao_id`,
`ItemProcessoCotacao.processo_cotacao_id`). Mesmo papel de
material_lookup.py/fornecedor_lookup.py.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao


def get_processo_cotacao(processo_cotacao_id: int | None) -> dict | None:
    """Resolve um ProcessoCotacao pelo id interno. Retorna dict (nunca ORM)."""
    if not processo_cotacao_id:
        return None
    obj = ProcessoCotacao.query.filter_by(id=processo_cotacao_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(ProcessoCotacao, "_display_field", "id")
    data["display"] = getattr(obj, display_field, None) or f"Processo #{obj.id}"
    return data
