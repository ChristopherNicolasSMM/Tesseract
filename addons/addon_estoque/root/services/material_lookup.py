"""
addons/addon_estoque/root/services/material_lookup.py

Ponto de acesso público e estável para outros Addons resolverem um
Material — chamada de service, nunca FK/ORM direta entre módulos
(skill 02). Mesmo papel de device_function_lookup.py em
addon_device_manager.

Este arquivo NÃO é gerado pelo CrudGen e não é sobrescrito por ele.

Por que `id` e não `name` como referência fraca aqui (ao contrário de
DeviceFunction, que usa name): decisão explícita do projeto — a chave
de referência fraca depende do caso, não segue um padrão único fixo.
`Material.nome` é único (unique=True) e pode ser usado por quem
preferir resolver por nome (get_material_by_nome), mas a referência
persistida em RecipeIngredient/Malte/Lupulo/Levedura/ItemEnvase é o
`id`.
"""
from __future__ import annotations

from addons.addon_estoque.root.model.material import Material
from addons.addon_estoque.root.model.saldo import Saldo


def get_material(material_id: int | None) -> dict | None:
    """Resolve um Material pelo id interno. Retorna dict (nunca ORM)."""
    if not material_id:
        return None
    obj = Material.query.filter_by(id=material_id, is_deleted=False).first()
    return obj.to_dict() if obj else None


def get_material_by_nome(nome: str | None) -> dict | None:
    """Resolve um Material pelo nome único (busca exata)."""
    if not nome:
        return None
    obj = Material.query.filter_by(nome=nome, is_deleted=False).first()
    return obj.to_dict() if obj else None


def buscar_material_por_termo(termo: str | None, limit: int = 10) -> list[dict]:
    """
    Busca aproximada por nome (LIKE, case-insensitive) — usada no
    fluxo de resolução de ingrediente (de-para) na importação de
    receita externa (feature_mash_control). Retorna candidatos, não
    um único resultado — a escolha final é do usuário ou do cache de
    mapeamento (IngredientMapping).
    """
    if not termo:
        return []
    padrao = f"%{termo.strip()}%"
    resultados = (
        Material.query
        .filter(Material.nome.ilike(padrao), Material.is_deleted.is_(False))
        .limit(limit)
        .all()
    )
    return [m.to_dict() for m in resultados]


def material_exists(material_id: int | None) -> bool:
    """Validação leve para uso em formulários/serviços de outro módulo."""
    if not material_id:
        return False
    return (
        Material.query
        .filter_by(id=material_id, is_deleted=False)
        .with_entities(Material.id)
        .first()
        is not None
    )


def get_saldo(material_id: int | None) -> dict | None:
    """Saldo atual de um Material — leitura, nunca escrita (escrita é
    sempre via estoque_service.registrar_movimentacao)."""
    if not material_id:
        return None
    saldo = Saldo.query.filter_by(material_id=material_id).first()
    return saldo.to_dict() if saldo else None
