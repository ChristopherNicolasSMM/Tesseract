"""API administrativa manual, descoberta pelo AddonBase."""
from flask import Blueprint, request, jsonify
from flask_login import login_required
from core.permissions import permission_required
from addons.addon_financeiro.root.model.monetary import Currency, MonetaryPolicy
from addons.addon_financeiro.root.services.monetary_service import create_currency, create_policy

finance_api_bp = Blueprint('finance_setup_api', __name__, url_prefix='/api/financeiro')


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
