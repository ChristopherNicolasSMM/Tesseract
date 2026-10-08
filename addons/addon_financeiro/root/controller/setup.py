"""Configuração manual administrativa; nenhum CRUD monetário genérico."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required
from core.permissions import permission_required
from addons.addon_financeiro.root.model.monetary import Currency, MonetaryPolicy
from addons.addon_financeiro.root.services.monetary_service import create_currency, create_policy
from services.core.organization_service import list_organizations

finance_setup_bp = Blueprint('finance_setup', __name__, url_prefix='/financeiro')
currencies_bp = Blueprint('currencies', __name__, url_prefix='/financeiro/currencies')
policies_bp = Blueprint('monetary_policies', __name__, url_prefix='/financeiro/monetary-policies')


def render_panel(kind, *, submitted=None, error=None, status=200):
    from core.admin_list_helpers import paginate
    search = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    query = Currency.query.order_by(Currency.code) if kind == 'currencies' else MonetaryPolicy.query.order_by(MonetaryPolicy.organization_code)
    if search:
        pattern = f'%{search}%'
        query = query.filter((Currency.code.ilike(pattern) | Currency.name.ilike(pattern)) if kind == 'currencies' else (MonetaryPolicy.organization_code.ilike(pattern) | MonetaryPolicy.currency_code.ilike(pattern)))
    items, total, pages = paginate(query, page)
    return render_template('financeiro/setup.html', panel=kind, items=items, search=search,
                           page=page, total=total, pages=pages, submitted=submitted or {}, form_error=error,
                           currencies=Currency.query.order_by(Currency.code).all(), organizations=list_organizations()), status


@finance_setup_bp.get('/')
@login_required
@permission_required('admin')
def manage():
    return redirect(url_for('currencies.list'))


@currencies_bp.get('/', endpoint='list')
@login_required
@permission_required('currencies.list')
def currency_list():
    return render_panel('currencies')


@policies_bp.get('/', endpoint='list')
@login_required
@permission_required('monetary_policies.list')
def policy_list():
    return render_panel('policies')


@finance_setup_bp.route('/<kind>', methods=['POST'])
@login_required
@permission_required('admin')
def save(kind):
    if kind not in {'currencies', 'policies'}:
        return '', 404
    data = request.form.to_dict()
    if kind == 'currencies':
        try:
            data['decimal_places'] = int(data.get('decimal_places', ''))
        except ValueError:
            data['decimal_places'] = None
    result = (create_currency if kind == 'currencies' else create_policy)(data)
    if not result.success:
        return render_panel(kind, submitted=data, error=result.error, status=result.code)
    flash('Configuração salva.', 'success')
    return redirect(url_for('currencies.list' if kind == 'currencies' else 'monetary_policies.list'))
