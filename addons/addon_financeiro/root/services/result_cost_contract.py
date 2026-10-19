"""Integração opcional somente por DTO; nenhum ORM externo no Financeiro."""
from flask import current_app


def sources(organization_code):
    if 'estoque' not in current_app.module_manager.active_modules:
        return {'available':False,'items':[],'basis':'Estoque indisponível; cobertura de custos exige conferência manual explícita.'}
    from addons.addon_estoque.root.services.financial_cost_data import list_cost_sources
    data=list_cost_sources(organization_code)
    return {'available':True,'items':data['items'],'basis':'Saídas elegíveis exigem destinação e competência explícitas; consumo produtivo e envase são capitalização, sem despesa duplicada.'}


def cost_source(organization_code,movement_id):
    data=sources(organization_code)
    if not data['available']:raise ValueError('Addon Estoque indisponível.')
    row=next((row for row in data['items'] if row['movement_id']==movement_id),None)
    if not row or not row['eligible']:raise ValueError('Movimento não elegível: origem ausente, transferida, revertida ou capitalizada.')
    return row
