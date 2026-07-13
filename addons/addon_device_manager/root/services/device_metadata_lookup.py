"""
addons/addon_device_manager/root/services/device_metadata_lookup.py

Ponto de acesso público e estável pra resolver um DeviceMetadata por
`id` — usado por `@weak_ref` (skill 11) de campos que são FK real pra
esta tabela DENTRO do próprio Addon (ex.: `DeviceActor.device_id`,
skill 02 permite FK real nesse caso; o combo de busca é só UI, não
muda a constraint). Mesmo padrão de `device_function_lookup.py` —
NÃO gerado pelo CrudGen, não sobrescrito por ele.
"""
from __future__ import annotations

from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata


def get_device_metadata(device_id: int | None) -> dict | None:
    """Resolve um DeviceMetadata pelo id. Devolve dict (nunca o objeto
    ORM) com a chave "display" obrigatória (contrato skill 11 §4),
    calculada a partir do `@display_field` do próprio model."""
    if not device_id:
        return None
    obj = DeviceMetadata.query.filter_by(id=device_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(DeviceMetadata, "_display_field", "name")
    data["display"] = getattr(obj, display_field, None) or f"Dispositivo #{obj.id}"
    return data
