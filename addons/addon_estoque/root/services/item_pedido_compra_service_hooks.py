"""Overrides manuais: snapshots e manutenção seguem purchase_integrity_service."""


from .purchase_integrity_service import operate as _operate


def create_override(data):
    return _operate('item', 'create', data=data)


def update_override(id, data):
    return _operate('item', 'update', ident=id, data=data)


def trash_override(id):
    return _operate('item', 'trash', ident=id)


def restore_override(id):
    return _operate('item', 'restore', ident=id)


def delete_permanent_override(id):
    return _operate('item', 'delete_permanent', ident=id)
