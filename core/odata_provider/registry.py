"""
core/odata_provider/registry.py

Fase 10, Patch 2 — descobre em runtime quais models estão marcados com
@odata_expose (annotations/__init__.py), varrendo todos os models já
mapeados pelo SQLAlchemy (independe de Addon/Feature/Core — o
provedor local não sabe nem precisa saber a origem do model, só que
ele foi opt-in explicitamente). Sem cache: a varredura é barata (um
dict comprehension sobre o registry) e módulos podem ser
ativados/desativados entre requisições no Model Builder/Playground —
cachear aqui reintroduziria o mesmo tipo de bug já corrigido em
outras partes do projeto (cache furado ao trocar de módulo ativo).
"""
from __future__ import annotations

from core.db import db
from annotations import get_odata_expose_meta


def _all_mapped_classes():
    """Todas as classes db.Model mapeadas no momento da chamada."""
    seen = set()
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls not in seen:
            seen.add(cls)
            yield cls


def list_exposed_entities() -> dict[str, dict]:
    """Retorna {entity_name: {"model": cls, "permission_required": str|None}}
    para todo model com @odata_expose ativo."""
    result = {}
    for cls in _all_mapped_classes():
        meta = get_odata_expose_meta(cls)
        if meta is None:
            continue
        result[meta["entity_name"]] = {
            "model": cls,
            "permission_required": meta["permission_required"],
        }
    return result


def get_exposed_entity(entity_name: str) -> dict | None:
    return list_exposed_entities().get(entity_name)
