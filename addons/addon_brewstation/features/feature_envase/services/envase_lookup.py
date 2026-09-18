"""
addons/addon_brewstation/features/feature_envase/services/envase_lookup.py

Ponto de acesso público e estável pra resolver um Envase por `id` —
usado por `@weak_ref` de CalculoPrecificacao.envase_id (FK real dentro
da própria Feature, nullable — combo só é relevante quando o usuário
já quer vincular a um Envase existente).
"""
from __future__ import annotations

from addons.addon_brewstation.features.feature_envase.model.envase import Envase


def get_envase(envase_id: int | None) -> dict | None:
    if not envase_id:
        return None
    obj = Envase.query.filter_by(id=envase_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    data["display"] = f"Envase #{obj.id} — {obj.data_envase or ''}".strip(" —")
    return data
