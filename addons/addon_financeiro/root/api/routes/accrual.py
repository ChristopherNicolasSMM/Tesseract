"""Escritas administrativas de competência e leitura com permissão própria."""
from flask import Blueprint,request,jsonify
from flask_login import login_required,current_user
from core.permissions import permission_required
from ...services import accrual_service as s,result_closing_service as closing_service,result_dashboard_service as dashboard_service
from .treasury import response

api_bp=Blueprint('finance_results_api',__name__,url_prefix='/api/financeiro/results')


@api_bp.post('/classifications')
@login_required
@permission_required('admin')
def classify():return response(s.classify(request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/recognitions')
@login_required
@permission_required('admin')
def recognize():return response(s.recognize(request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/recognitions/preview')
@login_required
@permission_required('admin')
def preview():return response(s.preview(request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/recognitions/<int:row_id>/reverse')
@login_required
@permission_required('admin')
def reverse(row_id):return response(s.reverse(row_id,request.get_json(silent=True),actor=current_user.username))


@api_bp.get('/dre')
@login_required
@permission_required('financial_results.list')
def statement():
    try:
        options=request.args.to_dict()
        if options.get('cost_center_id','').isascii() and options.get('cost_center_id','').isdigit():options['cost_center_id']=int(options['cost_center_id'])
        return jsonify(success=True,item=s.statement(options))
    except ValueError as exc:return jsonify(success=False,error=str(exc)),422


@api_bp.get('/review')
@login_required
@permission_required('financial_results.list')
def review():
    try:return jsonify(success=True,item=s.review(request.args.get('organization_code')))
    except ValueError as exc:return jsonify(success=False,error=str(exc)),422


@api_bp.get('/dashboard')
@login_required
@permission_required('financial_results.list')
def dashboard():
    try:return jsonify(success=True,item=dashboard_service.dashboard(request.args.to_dict()))
    except ValueError as exc:return jsonify(success=False,error=str(exc)),422


@api_bp.get('/costs')
@login_required
@permission_required('financial_results.list')
def costs():
    try:return jsonify(success=True,item=s.cost_review(request.args.get('organization_code')))
    except ValueError as exc:return jsonify(success=False,error=str(exc)),422


@api_bp.post('/close')
@login_required
@permission_required('admin')
def close():return response(closing_service.close(request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/closures/<int:row_id>/reopen')
@login_required
@permission_required('admin')
def reopen(row_id):return response(closing_service.reopen(row_id,request.get_json(silent=True),actor=current_user.username))


@api_bp.get('/closures/<int:row_id>')
@login_required
@permission_required('financial_results.list')
def closure(row_id):
    try:
        options=s.t.fields(request.args.to_dict(),{'organization_code'})
        value=closing_service.detail(options['organization_code'],row_id)
        if value is None:return jsonify(success=False,error='Fechamento não encontrado nesta organização.'),404,{'Cache-Control':'no-store'}
        return jsonify(success=True,item=value),200,{'Cache-Control':'no-store'}
    except ValueError as exc:return jsonify(success=False,error=str(exc)),422,{'Cache-Control':'no-store'}
