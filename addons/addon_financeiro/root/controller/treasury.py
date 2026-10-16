"""Telas manuais com endpoints list para descoberta padrão do addon."""
from datetime import date
from flask import Blueprint, request, render_template, redirect, url_for, abort, flash
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from services.core.organization_service import list_organizations, resolve_organization_by_code
from ..services import treasury_service as service
from ..services.exchange_service import stock_valuation_options
from ..services.treasury_purchase_contract import purchase_obligation
from ..model.treasury import (FinancialAccount as Account, FinancialCategory as Category, FinancialCostCenter as Center,
    FinancialTitle as Title, FinancialInstallment as Installment, FinancialSettlement as Settlement, FinancialMovement as Movement)

accounts_bp = Blueprint('financial_accounts', __name__, url_prefix='/financeiro/contas')
categories_bp = Blueprint('financial_categories', __name__, url_prefix='/financeiro/categorias')
centers_bp = Blueprint('financial_cost_centers', __name__, url_prefix='/financeiro/centros-custo')
titles_bp = Blueprint('financial_titles', __name__, url_prefix='/financeiro/titulos')
settlements_bp = Blueprint('financial_settlements', __name__, url_prefix='/financeiro/liquidacoes')
movements_bp = Blueprint('financial_movements', __name__, url_prefix='/financeiro/lancamentos')
ENDPOINTS = {'accounts': 'financial_accounts.list', 'categories': 'financial_categories.list', 'cost-centers': 'financial_cost_centers.list'}
LABELS = {'accounts': 'Contas financeiras', 'categories': 'Categorias financeiras', 'cost-centers': 'Centros de custo'}


def form_data():
    data = request.form.to_dict()
    data.pop('csrf_token', None)
    for field in ('policy_version_id', 'rate_id', 'category_id', 'cost_center_id', 'account_id', 'purchase_order_id'):
        if field in data:
            raw = data[field]
            if raw == '': data[field] = None
            elif raw.isascii() and raw.isdigit(): data[field] = int(raw)
            else: data[field] = raw  # serviço rejeita sem perder o valor digitado
    for field in ('installment_count', 'expected_version'):
        if field in data and data[field].isascii() and data[field].isdigit(): data[field] = int(data[field])
    if data.get('is_active') in ('true', 'false'): data['is_active'] = data['is_active'] == 'true'
    return data


def common(values=None):
    values = values or {}
    code = values.get('organization_code', request.args.get('organization_code', ''))
    try: options = stock_valuation_options(code) if code else stock_valuation_options()
    except ValueError: options = stock_valuation_options()
    return dict(values=values, organizations=list_organizations(), selected_code=code, options=options, today=date.today().isoformat())


def filtered(query, model, code=None):
    code = request.args.get('organization_code') if code is None else code
    if code:
        code = resolve_organization_by_code(code, require_active=False)['code']
        query = query.filter(model.organization_code == code)
    search = request.args.get('q', '').strip()
    if search:
        column = model.reference if model is Title else model.idempotency_key if model is Settlement else model.name
        query = query.filter(column.ilike(f'%{search}%'))
    return query


def render_catalog(kind, *, values=None, error=None, status=200):
    model = service.CATALOGS[kind]
    try:
        context = common(values)
        query = filtered(model.query, model, code=context['selected_code'])
    except ValueError as exc:
        query = model.query.filter(model.id < 0); context = common({}); error, status = str(exc), 422
    page = max(1, min(request.args.get('page', 1, type=int), 1000000))
    rows, total, pages = paginate(query.order_by(model.id.desc()), page)
    return render_template('financeiro/treasury/catalog.html', **context, kind=kind, label=LABELS[kind],
        endpoint=ENDPOINTS[kind], items=[row.to_dict() for row in rows], error=error, page=page, pages=pages,
        total=total, search=request.args.get('q', ''), edit_values=request.form.to_dict()), status


@accounts_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_accounts.list')
def accounts(): return render_catalog('accounts')


@categories_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_categories.list')
def categories(): return render_catalog('categories')


@centers_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_cost_centers.list')
def centers(): return render_catalog('cost-centers')


def save_catalog(kind):
    data = form_data(); result = service.create_catalog(kind, data, actor=current_user.username)
    if not result.success: return render_catalog(kind, values=request.form.to_dict(), error=result.error, status=result.code)
    flash('Cadastro financeiro criado.', 'success')
    return redirect(url_for(ENDPOINTS[kind], organization_code=result.data['organization_code']))


@accounts_bp.post('/')
@login_required
@permission_required('admin')
def create_account(): return save_catalog('accounts')


@categories_bp.post('/')
@login_required
@permission_required('admin')
def create_category(): return save_catalog('categories')


@centers_bp.post('/')
@login_required
@permission_required('admin')
def create_center(): return save_catalog('cost-centers')


@accounts_bp.post('/<int:row_id>/editar')
@login_required
@permission_required('admin')
def edit_account(row_id): return edit_catalog('accounts', row_id)


@categories_bp.post('/<int:row_id>/editar')
@login_required
@permission_required('admin')
def edit_category(row_id): return edit_catalog('categories', row_id)


@centers_bp.post('/<int:row_id>/editar')
@login_required
@permission_required('admin')
def edit_center(row_id): return edit_catalog('cost-centers', row_id)


def edit_catalog(kind, row_id):
    data = form_data(); data.pop('edit_id', None)
    result = service.edit_catalog(kind, row_id, data, actor=current_user.username)
    if not result.success: return render_catalog(kind, error=result.error, status=result.code)
    flash('Cadastro atualizado. Histórico preservado.', 'success')
    return redirect(url_for(ENDPOINTS[kind], organization_code=result.data['organization_code']))


def title_panel(*, values=None, error=None, status=200, preview=None):
    values = dict(values or {})
    if not values and request.args.get('purchase_order_id'):
        if not current_user.has_permission('pedido_compras.detail'): abort(403)
        try:
            source = purchase_obligation(int(request.args['purchase_order_id']))
            values.update(organization_code=source['organization_code'], currency_code=source['currency_code'], amount=source['amount'],
                counterparty=source['counterparty'], kind='PAYABLE', reference=f'Pedido #{source["order_id"]}', purchase_order_id=source['order_id'])
        except ValueError as exc:
            error, status = str(exc), 422
    try:
        context = common(values)
        query = filtered(Title.query, Title, code=context['selected_code'])
    except ValueError as exc:
        context = common({}); query = Title.query.filter(Title.id < 0); error, status = str(exc), 422
    kind = request.args.get('kind')
    if kind in ('PAYABLE', 'RECEIVABLE'): query = query.filter_by(kind=kind)
    page = max(1, min(request.args.get('page', 1, type=int), 1000000))
    rows, total, pages = paginate(query.order_by(Title.id.desc()), page)
    cats = Category.query.filter_by(is_active=True); centers = Center.query.filter_by(is_active=True)
    if context['selected_code']:
        cats = cats.filter_by(organization_code=context['selected_code']); centers = centers.filter_by(organization_code=context['selected_code'])
    return render_template('financeiro/treasury/titles.html', **context, items=[service.title_detail(row.id) for row in rows],
        categories=cats.order_by(Category.name).all(), centers=centers.order_by(Center.name).all(),
        error=error, page=page, pages=pages, total=total, search=request.args.get('q', ''), kind_filter=kind, title_preview=preview), status


@titles_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_titles.list')
def titles(): return title_panel()


@titles_bp.post('/')
@login_required
@permission_required('admin')
def create_title():
    data = form_data(); action = data.pop('action', 'confirm')
    if action not in ('preview', 'confirm'): return title_panel(values=request.form.to_dict(), error='Ação inválida.', status=422)
    result = (service.preview_title if action == 'preview' else service.create_title)(data, actor=current_user.username)
    if not result.success: return title_panel(values=request.form.to_dict(), error=result.error, status=result.code)
    if action == 'preview': return title_panel(values=request.form.to_dict(), preview=result.data)
    flash('Título e parcelas registrados.', 'success')
    return redirect(url_for('financial_titles.detail', row_id=result.data['id']))


def detail_panel(row_id, *, error=None, status=200, preview=None, installment_id=None):
    try: item = service.title_detail(row_id)
    except ValueError: abort(404)
    accounts = Account.query.filter_by(organization_code=item['organization_code'], is_active=True).order_by(Account.name).all()
    return render_template('financeiro/treasury/title_detail.html', item=item, accounts=accounts,
        options=stock_valuation_options(item['organization_code']), today=date.today().isoformat(), values=request.form.to_dict(),
        error=error, preview=preview, selected_installment=installment_id), status


@titles_bp.get('/<int:row_id>', endpoint='detail')
@login_required
@permission_required('financial_titles.list')
def title_detail(row_id): return detail_panel(row_id)


@titles_bp.post('/<int:row_id>/cancelar')
@login_required
@permission_required('admin')
def cancel(row_id):
    result = service.cancel_title(row_id, form_data(), actor=current_user.username)
    if not result.success: return detail_panel(row_id, error=result.error, status=result.code)
    flash('Título cancelado; histórico mantido.', 'success')
    return redirect(url_for('financial_titles.detail', row_id=row_id))


@settlements_bp.post('/parcelas/<int:row_id>/baixar')
@login_required
@permission_required('admin')
def settle(row_id):
    row = service.db.session.get(Installment, row_id)
    if row is None: abort(404)
    title_id = row.title_id
    data = form_data(); action = data.pop('action', 'confirm')
    if action not in ('preview', 'confirm'): return detail_panel(title_id, error='Ação inválida.', status=422)
    result = (service.preview_settlement if action == 'preview' else service.settle)(row_id, data, actor=current_user.username)
    if not result.success: return detail_panel(title_id, error=result.error, status=result.code, installment_id=row_id)
    if action == 'preview': return detail_panel(title_id, preview=result.data, installment_id=row_id)
    flash('Baixa registrada na conta financeira.', 'success')
    return redirect(url_for('financial_titles.detail', row_id=title_id))


@settlements_bp.post('/<int:row_id>/estornar')
@login_required
@permission_required('admin')
def reverse(row_id):
    row = service.db.session.get(Settlement, row_id)
    if row is None: abort(404)
    title_id = service.db.session.get(Installment, row.installment_id).title_id
    result = service.reverse(row_id, form_data(), actor=current_user.username)
    if not result.success: return detail_panel(title_id, error=result.error, status=result.code)
    flash('Baixa estornada e parcela reaberta.', 'success')
    return redirect(url_for('financial_titles.detail', row_id=title_id))


@settlements_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_settlements.list')
def settlements():
    try: query = filtered(Settlement.query, Settlement)
    except ValueError as exc: return str(exc), 422
    page = max(1, min(request.args.get('page', 1, type=int), 1000000)); rows, total, pages = paginate(query.order_by(Settlement.id.desc()), page)
    return render_template('financeiro/treasury/history.html', mode='settlements', items=[service.settlement_detail(row) for row in rows],
        **common(), page=page, total=total, pages=pages, search=request.args.get('q', ''))


@movements_bp.get('/', endpoint='list')
@login_required
@permission_required('financial_movements.list')
def movements():
    query = Movement.query.join(Account)
    try:
        if request.args.get('organization_code'):
            org = resolve_organization_by_code(request.args['organization_code'], require_active=False)['code']; query = query.filter(Account.organization_code == org)
        if request.args.get('account_id'): query = query.filter(Movement.account_id == int(request.args['account_id']))
        context = common()
    except ValueError as exc: return str(exc), 422
    page = max(1, min(request.args.get('page', 1, type=int), 1000000)); rows, total, pages = paginate(query.order_by(Movement.id.desc()), page)
    return render_template('financeiro/treasury/history.html', mode='movements', items=[row.to_dict() for row in rows],
        **context, page=page, total=total, pages=pages, search='')
