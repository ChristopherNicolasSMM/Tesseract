"""
addons/addon_estoque/root/services/material_unidade_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos
"""


def pai_apply_fields(obj, data):
    if obj.fator_para_base is None or obj.fator_para_base <= 0:
        raise ValueError("O fator para a unidade-base deve ser maior que zero.")
    if obj.is_unidade_base and obj.fator_para_base != 1:
        raise ValueError("A unidade-base deve ter fator igual a 1.")
    if obj.is_unidade_base:
        from core.db import db
        from addons.addon_estoque.root.model.material import Material
        material = db.session.get(Material, obj.material_id)
        if material is not None:
            material.unidade_medida = obj.unidade
