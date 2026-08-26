"""
addons/addon_estoque/root/services/item_pedido_compra_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

CUSTOMIZAÇÃO (skill 23, Fase 4): `fator_conversao_aplicado` (snapshot
de MaterialUnidade.fator_para_base no momento do save — nunca
recalculado depois, mesmo se o fator do cadastro mudar),
`quantidade_convertida_base` e `subtotal` são sempre CALCULADOS aqui,
nunca aceitos do payload (readonly_fields no model, skill 20) — roda
em pai_apply_fields porque precisa de material_unidade_id/quantidade/
preco_unitario já aplicados no obj.
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
