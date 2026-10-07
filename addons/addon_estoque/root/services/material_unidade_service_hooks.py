"""Overrides manuais de manutenção; regras fora do service gerado."""

from .material_unit_integrity_service import operate as _operate


def create_override(data):
    return _operate("create", data=data)


def update_override(id, data):
    return _operate("update", ident=id, data=data)


def trash_override(id):
    return _operate("trash", ident=id)


def restore_override(id):
    return _operate("restore", ident=id)


def delete_permanent_override(id):
    return _operate("delete_permanent", ident=id)


def inactivate_many_override(ids):
    results = []
    for ident in ids:
        result = _operate('update', ident=ident, data={'ativo': False})
        results.append({'id': ident, 'sucesso': result.success,
                        'erro': None if result.success else result.error})
    return {'resultados': results}
