"""
addons/addon_brewstation/features/feature_device_manager/services/device_function_lookup.py

Ponto de acesso público e estável para outros módulos resolverem uma
DeviceFunction por `name` (chave única e estável) — chamada de
service, nunca FK/ORM direta entre módulos (skill 02).

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele —
ao contrário de `device_function_service.py`. É o ponto de extensão
manual estável para resolução cross-módulo, equivalente em espírito
ao papel que um arquivo `_hooks.py` desempenha para customização.

Por que `name` e não `id`/`external_id` como referência fraca:
`DeviceFunction.name` já é a chave de negócio estável e única
(@required, unique=True) — usá-la como referência fraca evita
depender do `id` interno (que muda de significado se a tabela for
recriada) e evita adicionar um UUID novo só para este propósito.
"""
from __future__ import annotations

from addons.addon_device_manager.root.model.device_function import DeviceFunction


def get_function_by_name(name: str | None) -> dict | None:
    """
    Resolve uma DeviceFunction pelo nome único. Retorna um dict (nunca
    o objeto ORM) — quem chama (outro módulo) nunca deve manter uma
    referência viva ao objeto SQLAlchemy de um Addon diferente.
    """
    if not name:
        return None
    obj = DeviceFunction.query.filter_by(name=name, is_deleted=False).first()
    return obj.to_dict() if obj else None


def function_exists(name: str | None) -> bool:
    """Validação leve para uso em formulários/serviços de outro módulo."""
    if not name:
        return False
    return (
        DeviceFunction.query
        .filter_by(name=name, is_deleted=False)
        .with_entities(DeviceFunction.id)
        .first()
        is not None
    )
