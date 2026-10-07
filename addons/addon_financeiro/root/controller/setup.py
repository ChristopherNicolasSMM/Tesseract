"""Configuração manual administrativa; nenhum CRUD monetário genérico."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required
from core.permissions import permission_required
from addons.addon_financeiro.root.model.monetary import Currency, MonetaryPolicy
from addons.addon_financeiro.root.services.monetary_service import create_currency, create_policy
from services.core.organization_service import list_organizations

finance_setup_bp = Blueprint('finance_setup', __name__, url_prefix='/financeiro')
finance_api_bp = Blueprint('finance_setup_api', __name__, url_prefix='/api/financeiro')


@finance_setup_bp.route('/')
@login_required
@permission_required('admin')
def manage():
    return render_template('financeiro/setup.html', currencies=Currency.query.order_by(Currency.code).all(),
                           policies=MonetaryPolicy.query.order_by(MonetaryPolicy.organization_code).all(),
                           organizations=list_organizations())


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
    flash('Configuração salva.' if result.success else result.error, 'success' if result.success else 'error')
    return redirect(url_for('finance_setup.manage'))


@finance_api_bp.route('/currencies', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def currencies():
    if request.method == 'GET':
        return jsonify(success=True, items=[obj.to_dict() for obj in Currency.query.order_by(Currency.code).all()])
    result = create_currency(request.get_json(silent=True))
    return jsonify(success=result.success, item=result.data, error=result.error), result.code


@finance_api_bp.route('/policies', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def policies():
    if request.method == 'GET':
        return jsonify(success=True, items=[obj.to_dict() for obj in MonetaryPolicy.query.order_by(MonetaryPolicy.organization_code).all()])
    result = create_policy(request.get_json(silent=True))
    return jsonify(success=result.success, item=result.data, error=result.error), result.code
