"""
addons/addon_estoque/root/services/transportadora_lookup.py

Ponto de acesso público e estável para resolver uma Transportadora —
mesmo papel/mesma correção de fornecedor_lookup.py (ver esse arquivo
para o detalhe completo do achado).

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.transportadora import Transportadora


def get_transportadora(transportadora_id: int | None) -> dict | None:
    """Resolve uma Transportadora pelo id interno. Retorna dict (nunca ORM)."""
    if not transportadora_id:
        return None
    obj = Transportadora.query.filter_by(id=transportadora_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_attr = getattr(Transportadora, "_display_field", "id")
    data["display"] = getattr(obj, display_attr, None) or f"Transportadora #{obj.id}"
    return data


def transportadora_exists(transportadora_id: int | None) -> bool:
    if not transportadora_id:
        return False
    return (
        Transportadora.query
        .filter_by(id=transportadora_id, is_deleted=False)
        .with_entities(Transportadora.id)
        .first()
        is not None
    )
