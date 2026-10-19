from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from core.permissions import permission_required
from ...services import cash_operations_service as operations, cash_flow_service as flow
from .treasury import response

api_bp=Blueprint('finance_cash_api',__name__,url_prefix='/api/financeiro/operations')


def selection():
    value=request.args.to_dict()
    if value.get('account_id','').isascii() and value.get('account_id','').isdigit(): value['account_id']=int(value['account_id'])
    return value


@api_bp.get('/cash-flow')
@login_required
@permission_required('admin')
def cash_flow():
    try: return jsonify(success=True,item=flow.cash_flow(selection()))
    except ValueError as exc: return jsonify(success=False,error=str(exc)),422


@api_bp.post('/transfers')
@login_required
@permission_required('admin')
def transfer(): return response(operations.transfer(request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/transfers/<int:row_id>/reverse')
@login_required
@permission_required('admin')
def reverse_transfer(row_id): return response(operations.reverse_transfer(row_id,request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/statements/preview')
@login_required
@permission_required('admin')
def preview_statement(): return response(operations.preview_statement(request.get_json(silent=True)))


@api_bp.post('/statements')
@login_required
@permission_required('admin')
def import_statement(): return response(operations.import_statement(request.get_json(silent=True),actor=current_user.username))


@api_bp.get('/reconciliation')
@login_required
@permission_required('admin')
def reconciliation():
    try: return jsonify(success=True,item=flow.reconciliation_data(selection()))
    except ValueError as exc: return jsonify(success=False,error=str(exc)),422


@api_bp.post('/statement-lines/<int:row_id>/reconcile')
@login_required
@permission_required('admin')
def reconcile(row_id): return response(operations.reconcile(row_id,request.get_json(silent=True),actor=current_user.username))


@api_bp.post('/reconciliations/<int:row_id>/undo')
@login_required
@permission_required('admin')
def undo(row_id): return response(operations.undo_reconciliation(row_id,request.get_json(silent=True),actor=current_user.username))
