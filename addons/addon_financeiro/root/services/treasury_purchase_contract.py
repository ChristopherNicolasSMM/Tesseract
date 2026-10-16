"""Fronteira opcional com Compras, somente pelo DTO público de Estoque."""
from flask import current_app


def purchase_obligation(order_id, *, reserve=False):
    manager = current_app.module_manager
    if 'estoque' not in manager.active_modules:
        raise ValueError('Ative o addon Estoque para vincular um pedido de compra.')
    from addons.addon_estoque.root.services.estoque_service import consultar_obrigacao_pedido
    return consultar_obrigacao_pedido(order_id, reserve=reserve)
