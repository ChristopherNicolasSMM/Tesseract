"""Hooks manuais de Material: preservam pais e referências ao arquivar."""
from .material_unit_integrity_service import maintain_material as _maintain


def trash_override(id):
    return _maintain('trash', id)


def restore_override(id):
    return _maintain('restore', id)


def delete_permanent_override(id):
    return _maintain('delete_permanent', id)
