"""
addons/addon_estoque/root/services/endereco_lookup.py

Ponto de acesso público e estável para resolver um Endereco — mesmo
papel/mesma correção de fornecedor_lookup.py (ver esse arquivo para o
detalhe completo do achado). Usado como resolver do @weak_ref em
FornecedorEndereco.endereco_id/TransportadoraEndereco.endereco_id.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.endereco import Endereco


def get_endereco(endereco_id: int | None) -> dict | None:
    """Resolve um Endereco pelo id interno. Retorna dict (nunca ORM)."""
    if not endereco_id:
        return None
    obj = Endereco.query.filter_by(id=endereco_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_attr = getattr(Endereco, "_display_field", "id")
    data["display"] = getattr(obj, display_attr, None) or f"Endereço #{obj.id}"
    return data
