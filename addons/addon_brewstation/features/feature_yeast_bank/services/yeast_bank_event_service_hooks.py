"""
addons/addon_brewstation/features/feature_yeast_bank/services/yeast_bank_event_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos
"""


# Regras manuais preservadas ao regenerar o CRUD.
from .yeast_integrity_service import operate as _operate


def create_override(data):
    return _operate('event', 'create', data=data)


def update_override(id, data):
    return _operate('event', 'update', ident=id, data=data)


def trash_override(id):
    return _operate('event', 'trash', ident=id)


def restore_override(id):
    return _operate('event', 'restore', ident=id)


def delete_permanent_override(id):
    return _operate('event', 'delete_permanent', ident=id)
