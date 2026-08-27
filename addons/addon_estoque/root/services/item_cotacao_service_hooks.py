"""
addons/addon_estoque/root/services/item_cotacao_service_hooks.py

Criado UMA ÚNICA VEZ pelo CrudGen — nunca sobrescrito, mesmo com
--overwrite (skill 00/01). Customize aqui sem editar o service gerado.

Hooks disponíveis (todos opcionais):
    pbo_apply_fields(obj, data) -> dict | None   # antes de aplicar campos
    pai_apply_fields(obj, data) -> None          # depois de aplicar campos

REESTRUTURADO (achado do Christopher, sessão pós-Fase 6.3): antes lia
`obj.material_unidade_id`/`obj.quantidade` como colunas próprias.
Agora esses dois vêm do ItemProcessoCotacao pai (via `@property` no
model — obj.material_unidade_id, obj.quantidade delegam pra lá,
considerando quantidade_ofertada quando preenchida) — o cálculo em si
não muda, só a origem do dado.
"""


def pai_apply_fields(obj, data):
    from core.db import db
    from addons.addon_estoque.root.model.item_processo_cotacao import ItemProcessoCotacao

    # Busca direto por id (não via obj.item_processo_cotacao, a
    # relationship) — obj ainda é transiente aqui (roda antes do
    # db.session.add() no service gerado), lazy-load de relationship
    # falha silenciosamente (retorna None) em objeto fora da sessão.
    # Achado real ao testar esta correção.
    item_pedido = None
    if obj.item_processo_cotacao_id is not None:
        item_pedido = db.session.get(ItemProcessoCotacao, obj.item_processo_cotacao_id)
        if item_pedido is not None and item_pedido.material_unidade is not None:
            obj.fator_conversao_aplicado = item_pedido.material_unidade.fator_para_base

    quantidade_efetiva = obj.quantidade_ofertada
    if quantidade_efetiva is None and item_pedido is not None:
        quantidade_efetiva = item_pedido.quantidade_desejada

    if quantidade_efetiva is not None and obj.fator_conversao_aplicado is not None:
        obj.quantidade_convertida_base = quantidade_efetiva * obj.fator_conversao_aplicado

    if quantidade_efetiva is not None and obj.preco_unitario is not None:
        obj.subtotal = quantidade_efetiva * obj.preco_unitario
