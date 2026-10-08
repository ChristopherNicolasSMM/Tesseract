"""Fronteira opcional: importar Estoque não ativa modelos do Financeiro."""
from flask import current_app


def available():
    return 'financeiro' in current_app.module_manager.active_modules


def _exchange():
    if not available():
        raise ValueError('Ative o addon Financeiro para operações monetárias organizacionais.')
    from addons.addon_financeiro.root.services import exchange_service
    return exchange_service


def text(value,limit,name):
    if not isinstance(value,str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f'{name}: informe texto de 1 a {limit} caracteres.')
    return value.strip()


def decimal_text(value,*,positive=False):
    return _exchange().decimal_text(value,positive=positive)


def day(value):
    return _exchange().day(value)


def preview_conversion(data):
    return _exchange().preview_conversion(data)


def resolve_selected_policy(code,**kwargs):
    _exchange()
    from addons.addon_financeiro.root.services.policy_version_service import resolve_selected_policy as resolve
    return resolve(code,**kwargs)


def rounding(policy):
    _exchange()
    from addons.addon_financeiro.root.services.monetary_service import ROUNDINGS
    return ROUNDINGS[policy['rounding']]


def stock_valuation_options(code=None):
    if not available():
        return {'available':False,'currencies':[],'rates':[],'versions':[],'initial_policy':None}
    return _exchange().stock_valuation_options(code) | {'available':True}
