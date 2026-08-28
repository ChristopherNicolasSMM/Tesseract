"""
addons/addon_estoque/root/services/fabricante_lookup.py

Ponto de acesso público e estável para resolver um Fabricante — mesmo
papel/mesma correção de fornecedor_lookup.py (skill 24, correção
pós-Fase 6.3). Usado como resolver do @weak_ref em Material.fabricante_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.fabricante import Fabricante


def get_fabricante(fabricante_id: int | None) -> dict | None:
    """Resolve um Fabricante pelo id interno. Retorna dict (nunca ORM)."""
    if not fabricante_id:
        return None
    obj = Fabricante.query.filter_by(id=fabricante_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    data["display"] = obj.nome or f"Fabricante #{obj.id}"
    return data
