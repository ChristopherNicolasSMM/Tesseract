"""
core/odata_provider/service.py

Fase 10, Patch 2 — execução real de query/patch contra entidades
@odata_expose, com dois pontos de entrada:
- Usados pelas rotas HTTP (api/routes/core/odata_provider.py), para
  consumidores externos.
- Usados diretamente pelo atalho em processo de
  core/odata/connection_manager.py, quando ODataConnection.is_local —
  mesmo contrato de retorno em ambos os casos (dict pronto pra
  json.dumps), só sem o round-trip de rede no segundo caso.

Controle de acesso (decisão registrada em BACKLOG.md, Fase 10): Role
via User.has_permission() — mesmo mecanismo já usado em
DesignerPage.permission_required. Sem permission_required declarado
em @odata_expose = público (qualquer usuário autenticado do
Tesseract; nunca anônimo de fora — ver EntityNotExposedError abaixo,
que também cobre "não expõe pra ninguém").
"""
from __future__ import annotations

from core.odata_provider.registry import get_exposed_entity

_DEFAULT_TOP = 50
_MAX_TOP = 200


class EntityNotExposedError(Exception):
    """A entidade não existe no provedor local (não tem @odata_expose)."""


class PermissionDeniedError(Exception):
    """Usuário autenticado, mas sem a permission_required da entidade."""


def _resolve_entity_or_raise(entity_name: str) -> dict:
    info = get_exposed_entity(entity_name)
    if info is None:
        raise EntityNotExposedError(entity_name)
    return info


def _check_permission(info: dict, user) -> None:
    perm = info["permission_required"]
    if perm is None:
        return
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDeniedError(perm)
    if not user.has_permission(perm):
        raise PermissionDeniedError(perm)


def _row_to_dict(instance) -> dict:
    if hasattr(instance, "to_dict"):
        return instance.to_dict()
    # Fallback genérico — só usado se o model não tiver to_dict()
    # próprio (todo model gerado pelo CrudGen já tem, ver skill 12).
    result = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        result[column.name] = value.isoformat() if hasattr(value, "isoformat") else value
    return result


def _apply_simple_filter(query, model, filter_expr: str):
    """$filter mínimo: `campo eq 'valor'` ou `campo eq valor`, várias
    condições unidas por ` and `. Não é um parser OData completo —
    cobre o caso de uso real do Designer (Ação de Dado com
    static_params simples); expressões mais ricas (`gt`/`lt`/`or`/
    funções) ficam para quando um caso de uso real pedir, em vez de
    implementar especulativamente."""
    for clause in filter_expr.split(" and "):
        clause = clause.strip()
        if not clause:
            continue
        parts = clause.split(" eq ", 1)
        if len(parts) != 2:
            continue
        field, raw_value = parts[0].strip(), parts[1].strip()
        column = getattr(model, field, None)
        if column is None:
            continue
        if raw_value.startswith("'") and raw_value.endswith("'"):
            value = raw_value[1:-1]
        elif raw_value.lower() in ("true", "false"):
            value = raw_value.lower() == "true"
        else:
            try:
                value = int(raw_value) if "." not in raw_value else float(raw_value)
            except ValueError:
                value = raw_value
        query = query.filter(column == value)
    return query


def query_local(entity_name: str, params: dict | None = None, user=None) -> dict:
    info = _resolve_entity_or_raise(entity_name)
    _check_permission(info, user)
    model = info["model"]
    params = params or {}

    query = model.query
    if hasattr(model, "is_deleted"):
        query = query.filter_by(is_deleted=False)

    filter_expr = params.get("$filter")
    if filter_expr:
        query = _apply_simple_filter(query, model, filter_expr)

    orderby = params.get("$orderby")
    if orderby:
        field, _, direction = orderby.strip().partition(" ")
        column = getattr(model, field, None)
        if column is not None:
            query = query.order_by(column.desc() if direction.lower() == "desc" else column.asc())

    count = query.count()

    try:
        top = min(int(params.get("$top", _DEFAULT_TOP)), _MAX_TOP)
    except (TypeError, ValueError):
        top = _DEFAULT_TOP
    try:
        skip = max(int(params.get("$skip", 0)), 0)
    except (TypeError, ValueError):
        skip = 0

    rows = query.offset(skip).limit(top).all()
    return {"value": [_row_to_dict(r) for r in rows], "@odata.count": count}


def patch_local(entity_name: str, key: str, data: dict, user=None) -> dict:
    from core.db import db

    info = _resolve_entity_or_raise(entity_name)
    _check_permission(info, user)
    model = info["model"]

    pk_value = int(key) if str(key).isdigit() else key
    instance = model.query.get(pk_value)
    if instance is None:
        raise ValueError(f"Registro {key!r} não encontrado em {entity_name!r}.")

    for field, value in data.items():
        if hasattr(instance, field) and field != "id":
            setattr(instance, field, value)
    db.session.commit()

    return _row_to_dict(instance)
