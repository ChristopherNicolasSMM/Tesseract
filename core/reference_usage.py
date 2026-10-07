"""Consulta de referências declaradas por annotations, sem domínio de addon.

Só consulta models mapeados e tabelas presentes. Inclui registros arquivados;
não varre JSON/snapshots nem presume referências de módulos não carregados.
Não devolve objetos ORM nem altera dados.
"""
from sqlalchemy import inspect, select
from annotations import get_weak_refs
from core.db import db


def has_declared_references(options, target_values, *, exclude_models=()):
    tables = set(inspect(db.session.connection()).get_table_names())
    for mapper in sorted(db.Model.registry.mappers, key=lambda m: m.local_table.name):
        cls = mapper.class_
        if cls in exclude_models or mapper.local_table.name not in tables:
            continue
        for ref in get_weak_refs(cls):
            if ref.get('options') != options:
                continue
            field = ref['field']
            target_field = ref.get('value_field') or 'id'
            if field not in cls.__table__.columns or target_field not in target_values:
                continue
            value = target_values[target_field]
            if value is not None and db.session.execute(
                select(getattr(cls, field)).where(getattr(cls, field) == value).limit(1)
            ).first() is not None:
                return True
    return False
