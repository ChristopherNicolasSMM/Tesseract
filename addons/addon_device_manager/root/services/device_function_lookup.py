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

    Serve também de `resolver=` pra `@weak_ref` (skill 11) — a chave
    "display" é obrigatória nesse contrato, calculada a partir do
    `@display_field` do próprio DeviceFunction (nunca hardcoded aqui).
    """
    if not name:
        return None
    obj = DeviceFunction.query.filter_by(name=name, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(DeviceFunction, "_display_field", "name")
    data["display"] = getattr(obj, display_field, None) or f"Função #{obj.id}"
    return data


def get_function_by_id(function_id: int | None) -> dict | None:
    """
    Mesma ideia de `get_function_by_name()`, mas pelo `id` — usado por
    `@weak_ref` de campos que são FK real pra esta tabela DENTRO do
    próprio Addon (ex.: `DeviceActor.function_id`, skill 02 permite FK
    real nesse caso; o combo de busca aqui é só UI, não muda a
    constraint). Referência CROSS-Addon continua sempre por `name`
    (`get_function_by_name`), nunca por este id interno.
    """
    if not function_id:
        return None
    obj = DeviceFunction.query.filter_by(id=function_id, is_deleted=False).first()
    if not obj:
        return None
    data = obj.to_dict()
    display_field = getattr(DeviceFunction, "_display_field", "name")
    data["display"] = getattr(obj, display_field, None) or f"Função #{obj.id}"
    return data


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
