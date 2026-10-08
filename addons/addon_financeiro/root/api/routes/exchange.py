from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from addons.addon_financeiro.root.model.exchange import ExchangeRate, MonetaryConversion
from addons.addon_financeiro.root.services.exchange_service import create_rate, preview_conversion, confirm_conversion

exchange_api_bp = Blueprint('finance_exchange_api', __name__, url_prefix='/api/financeiro')


def response(result):
    return jsonify(success=result.success, item=result.data, error=result.error), result.code


@exchange_api_bp.route('/rates', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def rates():
    if request.method == 'POST': return response(create_rate(request.get_json(silent=True), actor=current_user.username))
    return history(ExchangeRate)


def history(model):
    query = model.query.order_by(model.id.desc())
    if request.args.get('organization_code'):
        query = query.filter_by(organization_code=request.args['organization_code'])
    page = max(1, request.args.get('page', 1, type=int))
    items, total, pages = paginate(query, page)
    return jsonify(success=True, items=[item.to_dict() for item in items], page=page, total=total, pages=pages)


@exchange_api_bp.post('/conversions/preview')
@login_required
@permission_required('admin')
def preview():
    try: return jsonify(success=True, item=preview_conversion(request.get_json(silent=True)))
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 422


@exchange_api_bp.route('/conversions', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def conversions():
    if request.method == 'POST': return response(confirm_conversion(request.get_json(silent=True), actor=current_user.username))
    return history(MonetaryConversion)
