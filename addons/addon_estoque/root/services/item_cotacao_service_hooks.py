"""
addons/addon_estoque/root/services/item_cotacao_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (skill 24, Fase 6.1): mesmo cálculo de
item_pedido_compra_service_hooks.py (skill 23, Fase 4) —
fator_conversao_aplicado/quantidade_convertida_base/subtotal sempre
calculados aqui, nunca aceitos do payload (readonly_fields no model).
"""


def pai_apply_fields(obj, data):
    from core.db import db
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade

    if obj.material_unidade_id is not None:
        unidade = db.session.get(MaterialUnidade, obj.material_unidade_id)
        if unidade is not None:
            obj.fator_conversao_aplicado = unidade.fator_para_base

    if obj.quantidade is not None and obj.fator_conversao_aplicado is not None:
        obj.quantidade_convertida_base = obj.quantidade * obj.fator_conversao_aplicado

    if obj.quantidade is not None and obj.preco_unitario is not None:
        obj.subtotal = obj.quantidade * obj.preco_unitario
