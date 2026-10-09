"""Telas manuais e guarda das APIs legadas; nenhum arquivo gerado alterado."""
from flask import request, jsonify, render_template, abort, redirect, flash, url_for
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.db import db
from addons.addon_estoque.root.services.purchase_pricing_service import (
    pricing_document, get_pricing, active_items, freeze, comparison)
from addons.addon_estoque.root.services.financial_stock_contract import stock_valuation_options
from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
from addons.addon_estoque.root.model.purchase_pricing import PurchasePricing


def _view(kind, ident, process_id=None):
    try:
        obj = pricing_document(kind, ident)
        if process_id is not None and obj.processo_cotacao_id != process_id:
            abort(404)
    except ValueError:
        abort(404)
    status, values = 200, {}
    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.get_json(silent=True)
            else:
                values = request.form.to_dict()
                ids = request.form.getlist('item_id')
                if any(not i.isascii() or not i.isdigit() for i in ids):
                    raise ValueError('Identificadores de itens inválidos.')
                data = {'currency_code': values.get('currency_code'), 'freight': values.get('freight'),
                        'items': [{'id': int(i), 'quantity': values.get('quantity_' + i),
                                   'unit_price': values.get('unit_price_' + i)} for i in ids]}
            result = freeze(kind, ident, data, actor=current_user.username)
            if request.is_json:
                return jsonify(success=result.success, data=result.data, error=result.error), result.code
            if result.success:
                flash('Cadastro monetário congelado. Os valores exatos serão usados no pedido e no recebimento.', 'success')
                return redirect(request.path)
            status = result.code
            flash(result.error, 'error')
        except ValueError as exc:
            status = 422
            flash(str(exc), 'error')
    priced = get_pricing(kind, ident)
    if request.is_json:
        return jsonify(success=True, data=priced.to_dict() if priced else None)
    items = active_items(kind, ident)
    return render_template('purchase_pricing/manage.html', item=obj, kind=kind, items=items,
                           pricing=priced.to_dict() if priced else None, values=values,
                           options=stock_valuation_options(), process_id=process_id), status


@login_required
@permission_required('pedido_compras.update')
@permission_required('item_pedido_compras.update')
def order_pricing_view(id):
    return _view('order', id)


@login_required
@permission_required('processo_cotacaos.update')
@permission_required('cotacaos.update')
@permission_required('item_cotacaos.update')
def quotation_pricing_view(id, quotation_id):
    return _view('quotation', quotation_id, id)


@login_required
@permission_required('processo_cotacaos.detail')
@permission_required('item_cotacaos.list')
def process_comparison_view(id):
    try:
        data = comparison(id)
        return jsonify(success=True, **data)
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 422


def protect_legacy_quote_request():
    """CRUD antigo não oferece catch para trash/restore; rejeitar antes da escrita.

    A guarda ORM continua cobrindo serviços/importadores e geração interna.
    """
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    blueprint = request.blueprint
    if (request.endpoint or '').rsplit('.', 1)[-1] in ('selecionar_vencedor', 'desmarcar_vencedor'):
        return
    if blueprint not in ('cotacaos_api', 'item_cotacaos_api', 'item_processo_cotacaos_api'):
        return
    if not current_user.is_authenticated:
        return  # autenticação/permissão continuam sendo responsabilidade das rotas existentes
    action = (request.endpoint or '').rsplit('.', 1)[-1]
    permission = {'create_item': 'create', 'update_item': 'update', 'trash_item': 'trash',
                  'restore_item': 'restore', 'delete_permanent_item': 'delete_permanent'}.get(action)
    if permission and not current_user.has_permission(blueprint.removesuffix('_api') + '.' + permission):
        return
    ident = (request.view_args or {}).get('id')
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(success=False, error='Dados inválidos.'), 422
    protected = False
    if blueprint == 'cotacaos_api' and ident:
        protected = get_pricing('quotation', ident) is not None
    elif blueprint == 'item_cotacaos_api':
        item = db.session.get(ItemCotacao, ident) if ident else None
        quote_ids = [item.cotacao_id] if item else []
        if type(data.get('cotacao_id')) is int:
            quote_ids.append(data['cotacao_id'])
        protected = any(get_pricing('quotation', q) for q in quote_ids)
    elif blueprint == 'item_processo_cotacaos_api' and ident:
        protected = db.session.query(PurchasePricing.id).join(ItemCotacao,
            PurchasePricing.quotation_id == ItemCotacao.cotacao_id).filter(
            ItemCotacao.item_processo_cotacao_id == ident).first() is not None
    if protected:
        return jsonify(success=False, error='Cadastro monetário congelado; preserve este documento e crie outro rascunho.'), 422
