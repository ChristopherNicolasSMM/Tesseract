"""
core/odata_provider/metadata.py

Fase 10, Patch 2 — monta o metadata no MESMO formato JSON
("S2MOdataPy") que core/odata/connection_manager.py já reconhece
nativamente (`{"entities": [{"name","label","fields",...}]}`, ver
_normalize_json) — o provedor local não inventa um formato novo, só
preenche o que já era aceito. Enriquecido com um bloco "ui" por
entidade contendo enum/weak_ref já declarados via @enum_field/
@weak_ref (annotations/__init__.py) — informação que o OData EDMX
padrão não carrega, e que o CrudGen já tinha pronta para outro uso.
"""
from __future__ import annotations

from annotations import get_enum_fields, get_weak_refs

_SA_TYPE_MAP_SUBSTR = (
    ("Boolean", "BOOLEAN"),
    ("DateTime", "DATE"),
    ("Date", "DATE"),
    ("Time", "DATE"),
    ("Integer", "NUMBER"),
    ("Numeric", "NUMBER"),
    ("Float", "NUMBER"),
    ("String", "TEXT"),
    ("Text", "TEXT"),
    ("Unicode", "TEXT"),
    ("JSON", "TEXT"),
)


def _sa_type_to_odata_type(column_type) -> str:
    type_name = type(column_type).__name__
    for substr, odata_type in _SA_TYPE_MAP_SUBSTR:
        if substr in type_name:
            return odata_type
    return "TEXT"


def _column_to_field(column) -> dict:
    return {
        "name": column.name,
        "label": column.name,
        "type": _sa_type_to_odata_type(column.type),
        "required": not column.nullable,
        "max_length": getattr(column.type, "length", None),
    }


def _entity_ui(model) -> dict:
    enum_fields = {f["field"]: f["options"] for f in get_enum_fields(model)}
    weak_refs = {
        w["field"]: {"options": w["options"], "value_field": w["value_field"] or "id"}
        for w in get_weak_refs(model) if w.get("options")
    }
    ui = {}
    if enum_fields:
        ui["enum_fields"] = enum_fields
    if weak_refs:
        ui["weak_refs"] = weak_refs
    return ui


def build_entity_metadata(entity_name: str, model) -> dict:
    fields = [_column_to_field(c) for c in model.__table__.columns]
    label = getattr(model, "_entity_label", model.__name__)
    return {
        "name": entity_name,
        "label": label,
        "entity_type_name": model.__name__,
        "fields": fields,
        "ui": _entity_ui(model),
    }


def build_metadata_json() -> dict:
    from core.odata_provider.registry import list_exposed_entities

    entities = [
        build_entity_metadata(name, info["model"])
        for name, info in sorted(list_exposed_entities().items())
    ]
    return {"entities": entities, "_source_format": "json"}
