"""Telas manuais com descoberta automática de transações pelo addon."""
import uuid
from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from services.core.organization_service import list_organizations
from addons.addon_financeiro.root.model.monetary import Currency
from addons.addon_financeiro.root.model.exchange import ExchangeRate, MonetaryConversion
from addons.addon_financeiro.root.model.policy_version import MonetaryPolicyVersion
from addons.addon_financeiro.root.services.exchange_service import create_rate, preview_conversion, confirm_conversion

rates_bp = Blueprint('exchange_rates', __name__, url_prefix='/financeiro/exchange-rates')
conversions_bp = Blueprint('monetary_conversions', __name__, url_prefix='/financeiro/conversions')


def panel(kind, submitted=None, error=None, preview=None, status=200):
    model = ExchangeRate if kind == 'rates' else MonetaryConversion
    search = (request.args.get('q') or '').strip()
    page = max(1, request.args.get('page', 1, type=int))
    query = model.query.order_by(model.id.desc())
    if search:
        field = model.source if kind == 'rates' else model.reference
        query = query.filter(model.organization_code.ilike(f'%{search}%') | field.ilike(f'%{search}%'))
    items, total, pages = paginate(query, page)
    submitted = submitted if submitted is not None else {'idempotency_key': str(uuid.uuid4())}
    return render_template('financeiro/exchange.html', panel=kind, items=[item.to_dict() for item in items], search=search, page=page, total=total, pages=pages, submitted=submitted, form_error=error, preview=preview, currencies=Currency.query.order_by(Currency.code).all(), organizations=list_organizations(), rates=ExchangeRate.query.order_by(ExchangeRate.id.desc()).all(), policy_versions=MonetaryPolicyVersion.query.order_by(MonetaryPolicyVersion.id.desc()).all()), status


@rates_bp.get('/', endpoint='list')
@login_required
@permission_required('exchange_rates.list')
def list_rates():
    return panel('rates')


@rates_bp.post('/')
@login_required
@permission_required('admin')
def save_rate():
    data = request.form.to_dict()
    result = create_rate(data, actor=current_user.username)
    if not result.success: return panel('rates', submitted=data, error=result.error, status=result.code)
    flash('Taxa cadastrada. Uma unidade da moeda original corresponde à taxa na moeda-base.', 'success')
    return redirect(url_for('exchange_rates.list'))


@conversions_bp.get('/', endpoint='list')
@login_required
@permission_required('monetary_conversions.list')
def list_conversions():
    return panel('conversions')


@conversions_bp.post('/')
@login_required
@permission_required('admin')
def convert():
    submitted = request.form.to_dict()
    data = dict(submitted)
    action = data.pop('action', '')
    try:
        data['rate_id'] = int(data['rate_id']) if data.get('rate_id') else None
        if 'policy_version_id' in data:
            data['policy_version_id'] = int(data['policy_version_id']) if data['policy_version_id'] else None
        if action == 'preview':
            preview = preview_conversion({k: v for k, v in data.items() if k not in {'idempotency_key', 'reference'}})
            return panel('conversions', submitted=submitted, preview=preview)
        if action != 'confirm': raise ValueError('Escolha simular ou confirmar.')
        result = confirm_conversion(data, actor=current_user.username)
        if not result.success: return panel('conversions', submitted=submitted, error=result.error, status=result.code)
    except ValueError as exc:
        return panel('conversions', submitted=submitted, error=str(exc), status=422)
    flash('Conversão confirmada no histórico.', 'success')
    return redirect(url_for('monetary_conversions.list'))
