"""API administrativa da tesouraria; os serviços nunca recebem autor do cliente."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from ...services import treasury_service as service
from ...model.treasury import FinancialTitle as Title, FinancialSettlement as Settlement, FinancialMovement as Movement, FinancialAccount as Account

api_bp = Blueprint('finance_treasury_api', __name__, url_prefix='/api/financeiro/treasury')


def response(result):
    return jsonify(success=result.success, item=result.data, error=result.error), result.code


def page(query, model):
    code = request.args.get('organization_code')
    if code:
        from services.core.organization_service import resolve_organization_by_code
        org = resolve_organization_by_code(code, require_active=False)['code']
        query = query.filter((Account.organization_code if model is Movement else model.organization_code) == org)
    index = max(1, min(request.args.get('page', 1, type=int), 1000000))
    rows, total, pages = paginate(query.order_by(model.id.desc()), index)
    return jsonify(success=True, items=[service.title_detail(row.id) if model is Title else service.settlement_detail(row) if model is Settlement else row.to_dict() for row in rows], page=index, total=total, pages=pages)


@api_bp.route('/catalogs/<kind>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def catalogs(kind):
    if kind not in service.CATALOGS: return jsonify(success=False, error='Cadastro inválido.'), 404
    if request.method == 'POST': return response(service.create_catalog(kind, request.get_json(silent=True), actor=current_user.username))
    try: return page(service.CATALOGS[kind].query, service.CATALOGS[kind])
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 422


@api_bp.patch('/catalogs/<kind>/<int:row_id>')
@login_required
@permission_required('admin')
def edit_catalog(kind, row_id):
    return response(service.edit_catalog(kind, row_id, request.get_json(silent=True), actor=current_user.username))


@api_bp.route('/titles', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def titles():
    if request.method == 'POST': return response(service.create_title(request.get_json(silent=True), actor=current_user.username))
    query = Title.query
    if request.args.get('kind') in ('PAYABLE', 'RECEIVABLE'): query = query.filter_by(kind=request.args['kind'])
    try: return page(query, Title)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 422


@api_bp.get('/titles/<int:row_id>')
@login_required
@permission_required('admin')
def title(row_id):
    try: return jsonify(success=True, item=service.title_detail(row_id))
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 404


@api_bp.post('/titles/<int:row_id>/cancel')
@login_required
@permission_required('admin')
def cancel(row_id): return response(service.cancel_title(row_id, request.get_json(silent=True), actor=current_user.username))


@api_bp.post('/installments/<int:row_id>/preview')
@login_required
@permission_required('admin')
def preview(row_id): return response(service.preview_settlement(row_id, request.get_json(silent=True), actor=current_user.username))


@api_bp.post('/installments/<int:row_id>/settle')
@login_required
@permission_required('admin')
def settle(row_id): return response(service.settle(row_id, request.get_json(silent=True), actor=current_user.username))


@api_bp.post('/settlements/<int:row_id>/reverse')
@login_required
@permission_required('admin')
def reverse(row_id): return response(service.reverse(row_id, request.get_json(silent=True), actor=current_user.username))


@api_bp.get('/settlements')
@login_required
@permission_required('admin')
def settlements():
    try: return page(Settlement.query, Settlement)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 422


@api_bp.get('/movements')
@login_required
@permission_required('admin')
def movements():
    query = Movement.query.join(Account)
    if request.args.get('account_id'):
        try: query = query.filter(Movement.account_id == int(request.args['account_id']))
        except ValueError: return jsonify(success=False, error='Conta inválida.'), 422
    try: return page(query, Movement)
    except ValueError as exc: return jsonify(success=False, error=str(exc)), 422


@api_bp.post('/titles/preview')
@login_required
@permission_required('admin')
def preview_title(): return response(service.preview_title(request.get_json(silent=True), actor=current_user.username))
