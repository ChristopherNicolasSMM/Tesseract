"""
addons/addon_estoque/root/services/material_unidade_lookup.py

Ponto de acesso público e estável para resolver uma MaterialUnidade —
mesmo papel/mesma correção de fornecedor_lookup.py (ver esse arquivo
para o detalhe completo do achado). Usado como resolver do @weak_ref
em ItemPedidoCompra.material_unidade_id/ItemCotacao.material_unidade_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.material_unidade import MaterialUnidade


def get_material_unidade(material_unidade_id: int | None) -> dict | None:
    """Resolve uma MaterialUnidade pelo id interno. Retorna dict (nunca ORM)."""
    if not material_unidade_id:
        return None
    obj = MaterialUnidade.query.filter_by(id=material_unidade_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_attr = getattr(MaterialUnidade, "_display_field", "id")
    data["display"] = getattr(obj, display_attr, None) or f"Unidade #{obj.id}"
    return data
