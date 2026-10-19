"""Operação manual no padrão de descoberta automática do Financeiro."""
from uuid import uuid4
from flask import Blueprint, request, render_template, redirect, flash, current_app
from .workspace import finance_url as url_for, today_date
from flask_login import login_required, current_user
from core.permissions import permission_required
from core.admin_list_helpers import paginate
from ..services import cash_operations_service as operations, cash_flow_service as flow
from ..model.cash_operations import FinancialTransfer as Transfer, BankStatement as Statement
from ..model.treasury import FinancialAccount as Account
from .treasury import common, form_data

transfers_bp=Blueprint('financial_transfers',__name__,url_prefix='/financeiro/transferencias')
reconciliations_bp=Blueprint('financial_reconciliations',__name__,url_prefix='/financeiro/conciliacao')
flow_bp=Blueprint('financial_cash_flow',__name__,url_prefix='/financeiro/fluxo-caixa')


def selection():
    today=today_date()
    value={'organization_code':request.args.get('organization_code',''),'date_from':request.args.get('date_from',today.replace(day=1).isoformat()),
        'date_to':request.args.get('date_to',today.isoformat())}
    if request.args.get('account_id'):
        raw=request.args['account_id']; value['account_id']=int(raw) if raw.isascii() and raw.isdigit() else raw
    return value


def panel(mode,*,error=None,status=200,preview=None,values=None):
    context=common(values); selected=selection(); code=context['selected_code']
    accounts=Account.query
    if code: accounts=accounts.filter_by(organization_code=code)
    data=None
    if code and mode in ('flow','reconciliation'):
        try: data=(flow.cash_flow if mode=='flow' else flow.reconciliation_data)(selected)
        except ValueError as exc: error,status=str(exc),422
    items=[]; total=0; pages=0
    page=max(1,min(request.args.get('page',1,type=int),1000000))
    if mode in ('transfers','reconciliation'):
        model=Transfer if mode=='transfers' else Statement
        query=model.query
        if code: query=query.filter_by(organization_code=code)
        if mode=='transfers':
            try: query=query.filter(Transfer.operation_date.between(flow.day(selected['date_from']),flow.day(selected['date_to'])))
            except ValueError as exc: query=query.filter(Transfer.id<0);error,status=str(exc),422
        if mode=='reconciliation' and selected.get('account_id'): query=query.filter_by(account_id=selected['account_id'])
        rows,total,pages=paginate(query.order_by(model.id.desc()),page)
        items=[operations.transfer_detail(row) if mode=='transfers' else row.to_dict() for row in rows]
    return render_template('financeiro/treasury/cash_operations.html',**context,mode=mode,error=error,data=data,
        items=items,accounts=accounts.order_by(Account.name).all(),selection=selected,new_key=uuid4().hex,
        preview=preview,page=page,pages=pages,total=total,reports_available='reports' in current_app.module_manager.active_modules),status


@flow_bp.get('/',endpoint='list')
@login_required
@permission_required('financial_movements.list')
@permission_required('financial_titles.list')
def cash_flow(): return panel('flow')


@transfers_bp.get('/',endpoint='list')
@login_required
@permission_required('financial_transfers.list')
def transfers(): return panel('transfers')


@transfers_bp.post('/')
@login_required
@permission_required('admin')
def create_transfer():
    data=form_data()
    for key in ('source_account_id','destination_account_id'):
        if isinstance(data.get(key),str) and data[key].isascii() and data[key].isdigit(): data[key]=int(data[key])
    result=operations.transfer(data,actor=current_user.username)
    if not result.success: return panel('transfers',values=request.form.to_dict(),error=result.error,status=result.code)
    flash('Transferência registrada nas duas contas.','success')
    return redirect(url_for('financial_transfers.list',organization_code=result.data['organization_code']))


@transfers_bp.post('/<int:row_id>/estornar')
@login_required
@permission_required('admin')
def reverse_transfer(row_id):
    result=operations.reverse_transfer(row_id,form_data(),actor=current_user.username)
    if not result.success: return panel('transfers',error=result.error,status=result.code)
    flash('Transferência estornada nas duas contas.','success')
    return redirect(url_for('financial_transfers.list',organization_code=result.data['organization_code']))


@reconciliations_bp.get('/',endpoint='list')
@login_required
@permission_required('financial_reconciliations.list')
@permission_required('financial_movements.list')
def reconciliation(): return panel('reconciliation')


@reconciliations_bp.post('/importar')
@login_required
@permission_required('admin')
def import_statement():
    data=form_data(); action=data.pop('action','preview')
    try:
        upload=request.files.get('statement')
        data['lines']=operations.csv_lines(upload.read(2*1024*1024+1) if upload else b'')
        if action not in ('preview','confirm'): raise ValueError('Ação inválida.')
    except ValueError as exc: return panel('reconciliation',values=request.form.to_dict(),error=str(exc),status=422)
    result=operations.preview_statement(data) if action=='preview' else operations.import_statement(data,actor=current_user.username)
    if not result.success: return panel('reconciliation',values=request.form.to_dict(),error=result.error,status=result.code)
    if action=='preview': return panel('reconciliation',values=request.form.to_dict(),preview=result.data)
    flash('Extrato importado sem alterar saldos.','success')
    return redirect(url_for('financial_reconciliations.list',organization_code=result.data['organization_code'],account_id=result.data['account_id']))


@reconciliations_bp.post('/linhas/<int:row_id>/conciliar')
@login_required
@permission_required('admin')
def reconcile(row_id):
    result=operations.reconcile(row_id,form_data(),actor=current_user.username)
    if not result.success: return panel('reconciliation',error=result.error,status=result.code)
    flash('Vínculo de conciliação registrado.','success')
    return redirect(url_for('financial_reconciliations.list',organization_code=result.data['organization_code'],account_id=result.data['account_id']))


@reconciliations_bp.post('/<int:row_id>/desfazer')
@login_required
@permission_required('admin')
def undo(row_id):
    result=operations.undo_reconciliation(row_id,form_data(),actor=current_user.username)
    if not result.success: return panel('reconciliation',error=result.error,status=result.code)
    flash('Conciliação desfeita; histórico preservado.','success')
    return redirect(url_for('financial_reconciliations.list',organization_code=result.data['organization_code']))
