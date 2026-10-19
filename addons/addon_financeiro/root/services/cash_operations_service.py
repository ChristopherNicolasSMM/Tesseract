"""Transferências e conciliação explícitas, sem criação implícita de baixas."""
import csv
import io
from decimal import Decimal
from core.db import db
from services.core.organization_service import Result, resolve_organization_by_code
from ..model.cash_operations import (FinancialTransfer as Transfer, FinancialTransferReversal as TransferReversal,
    BankStatement as Statement, BankStatementLine as Line, BankReconciliation as Link,
    BankReconciliationUndo as Undo, ActiveBankReconciliation as Active)
from . import treasury_service as t
from .exchange_service import text, day, decimal_text
from .policy_version_service import resolve_selected_policy


def replay(model, org, key, request):
    row = model.query.filter_by(organization_code=org, idempotency_key=key).first()
    if row and row.request_json != t.dump(request):
        raise ValueError('Chave já utilizada com conteúdo diferente.')
    return row


def transfer_detail(row):
    value = row.to_dict()
    reversal = TransferReversal.query.filter_by(transfer_id=row.id).first()
    value.update(status='REVERSED' if reversal else 'POSTED', reversal=reversal.to_dict() if reversal else None)
    return value


@t.transaction
def transfer(data, *, actor):
    actor = text(actor, 120, 'Autor')
    data = t.fields(data, {'organization_code','source_account_id','destination_account_id','amount','operation_date','policy_version_id','idempotency_key','notes'})
    org = resolve_organization_by_code(data['organization_code'], require_active=False)['code']
    source, dest = t.ident(data['source_account_id']), t.ident(data['destination_account_id'])
    if source == dest: raise ValueError('Selecione duas contas distintas.')
    operation_date = day(data['operation_date'])
    key = text(data['idempotency_key'],80,'Chave')
    value = t.amount(data['amount'], positive=True)
    request = {**data, 'organization_code':org, 'amount':t.canonical(value), 'idempotency_key':key,
        'notes':text(data['notes'],1000,'Observações') if data['notes'] else None}
    old = replay(Transfer,org,key,request)
    if old: return Result(True,data=transfer_detail(old))
    resolve_organization_by_code(org, require_active=True)
    accounts = {i:t.catalog_row(t.Account,i,org) for i in sorted((source,dest))}
    old = replay(Transfer,org,key,request)
    if old: return Result(True,data=transfer_detail(old))
    policy = resolve_selected_policy(org,policy_version_id=data['policy_version_id'],operation_date=data['operation_date'])
    t.amount(value, positive=True,scale=policy['decimal_places'])
    if any(a.currency_code != policy['currency_code'] for a in accounts.values()):
        raise ValueError('Transferência exige contas na mesma moeda base.')
    row = Transfer(organization_code=org,source_account_id=source,destination_account_id=dest,amount=value,
        operation_date=operation_date,idempotency_key=key,request_json=t.dump(request),snapshot_json=t.dump({'policy':policy,'notes':request['notes'],'source':accounts[source].name,
            'destination':accounts[dest].name,'source_balance_before':t.canonical(accounts[source].balance),
            'destination_balance_before':t.canonical(accounts[dest].balance)}),created_by=actor)
    db.session.add(row); db.session.flush()
    snapshot={'transfer_id':row.id,'policy':policy,'notes':request['notes'],'source':accounts[source].name,'destination':accounts[dest].name}
    t.post_cash(accounts[source],-value,operation_date,f'transfer:{row.id}:out',snapshot,actor)
    t.post_cash(accounts[dest],value,operation_date,f'transfer:{row.id}:in',snapshot,actor)
    return Result(True,data=transfer_detail(row),code=201)


@t.transaction
def reverse_transfer(row_id,data,*,actor):
    actor=text(actor,120,'Autor')
    data=t.fields(data,{'operation_date','reason','idempotency_key'})
    row=t.reserve(Transfer,row_id)
    request={**data,'transfer_id':row.id,'reason':text(data['reason'],1000,'Motivo'),'idempotency_key':text(data['idempotency_key'],80,'Chave')}
    date=day(data['operation_date'])
    old=replay(TransferReversal,row.organization_code,request['idempotency_key'],request)
    if old: return Result(True,data=old.to_dict())
    resolve_organization_by_code(row.organization_code,require_active=True)
    if TransferReversal.query.filter_by(transfer_id=row.id).first(): raise ValueError('Transferência já estornada.')
    if date<row.operation_date: raise ValueError('Estorno anterior à transferência.')
    accounts={i:t.reserve(t.Account,i) for i in sorted((row.source_account_id,row.destination_account_id))}
    reversal=TransferReversal(transfer_id=row.id,organization_code=row.organization_code,operation_date=date,
        reason=request['reason'],idempotency_key=request['idempotency_key'],request_json=t.dump(request),
        snapshot_json=t.dump({'transfer':row.to_dict()}),created_by=actor)
    db.session.add(reversal); db.session.flush()
    for account_id,delta,side in ((row.destination_account_id,-row.amount,'out'),(row.source_account_id,row.amount,'in')):
        t.post_cash(accounts[account_id],delta,date,f'transfer-reversal:{reversal.id}:{side}',
            {'transfer_id':row.id,'transfer_reversal_id':reversal.id,'reason':request['reason']},actor)
    return Result(True,data=reversal.to_dict(),code=201)


def csv_lines(raw):
    if not isinstance(raw,bytes) or len(raw)>2*1024*1024: raise ValueError('CSV excede 2 MiB.')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),strict=True)
        if reader.fieldnames != ['external_id','operation_date','amount','description']:
            raise ValueError('Cabeçalho: external_id,operation_date,amount,description')
        rows=[]
        for row in reader:
            if len(rows)>=2000: raise ValueError('Máximo de 2000 linhas por extrato.')
            rows.append(row)
        return rows
    except (UnicodeError,csv.Error) as exc: raise ValueError('CSV UTF-8 inválido.') from exc


def statement_request(data):
    data=t.fields(data,{'account_id','currency_code','reference','idempotency_key','lines'})
    account=db.session.get(t.Account,t.ident(data['account_id']))
    if account is None: raise ValueError('Conta não encontrada.')
    if data['currency_code']!=account.currency_code: raise ValueError('Moeda do extrato difere da conta.')
    if not isinstance(data['lines'],list) or not 1<=len(data['lines'])<=2000: raise ValueError('Extrato exige de 1 a 2000 linhas.')
    lines=[]; seen=set()
    for raw in data['lines']:
        raw=t.fields(raw,{'external_id','operation_date','amount','description'})
        external=text(raw['external_id'],120,'Identificador bancário')
        if external in seen: raise ValueError('Identificador bancário repetido no extrato.')
        seen.add(external)
        value=Decimal(decimal_text(raw['amount']))
        if not value: raise ValueError('Linha bancária não pode ser zero.')
        date=day(raw['operation_date'])
        if date<account.opening_date: raise ValueError('Linha anterior à abertura da conta.')
        lines.append({'external_id':external,'operation_date':date.isoformat(),'amount':t.canonical(value),
            'description':text(raw['description'],1000,'Descrição')})
    return account,{**data,'reference':text(data['reference'],120,'Referência'),
        'idempotency_key':text(data['idempotency_key'],80,'Chave'),'lines':lines}


def preview_statement(data):
    try:
        with db.session.no_autoflush:
            account,request=statement_request(data)
            return Result(True,data={**request,'organization_code':account.organization_code})
    except ValueError as exc: return Result(False,error=str(exc),code=422)


@t.transaction
def import_statement(data,*,actor):
    actor=text(actor,120,'Autor')
    account,request=statement_request(data)
    org=account.organization_code
    old=replay(Statement,org,request['idempotency_key'],request)
    if old: return Result(True,data=old.to_dict())
    resolve_organization_by_code(org,require_active=True)
    account=t.catalog_row(t.Account,account.id,org)
    old=replay(Statement,org,request['idempotency_key'],request)
    if old: return Result(True,data=old.to_dict())
    row=Statement(organization_code=org,account_id=account.id,currency_code=account.currency_code,
        reference=request['reference'],idempotency_key=request['idempotency_key'],request_json=t.dump(request),created_by=actor)
    db.session.add(row); db.session.flush()
    for line in request['lines']:
        db.session.add(Line(statement_id=row.id,account_id=account.id,external_id=line['external_id'],
            operation_date=day(line['operation_date']),amount=Decimal(line['amount']),description=line['description'],created_by=actor))
    db.session.flush()
    return Result(True,data=row.to_dict(),code=201)


def link_detail(row):
    value=row.to_dict()
    undo=Undo.query.filter_by(reconciliation_id=row.id).first()
    value.update(status='UNDONE' if undo else 'LINKED',undo=undo.to_dict() if undo else None)
    return value


@t.transaction
def reconcile(line_id,data,*,actor):
    actor=text(actor,120,'Autor')
    data=t.fields(data,{'movement_id','idempotency_key','date_difference_reason'})
    line=db.session.get(Line,t.ident(line_id))
    if line is None: raise ValueError('Linha bancária não encontrada.')
    account=t.reserve(t.Account,line.account_id)
    org=account.organization_code
    request={**data,'line_id':line.id,'movement_id':t.ident(data['movement_id']),
        'idempotency_key':text(data['idempotency_key'],80,'Chave'),
        'date_difference_reason':text(data['date_difference_reason'],1000,'Justificativa') if data['date_difference_reason'] else None}
    old=replay(Link,org,request['idempotency_key'],request)
    if old: return Result(True,data=link_detail(old))
    resolve_organization_by_code(org,require_active=True)
    movement=db.session.get(t.Movement,request['movement_id'])
    if movement is None or movement.account_id!=account.id or movement.amount_delta!=line.amount:
        raise ValueError('Conciliação exige mesma conta e montante com sinal idêntico.')
    if movement.operation_date!=line.operation_date and not request['date_difference_reason']:
        raise ValueError('Datas diferentes exigem justificativa explícita.')
    if db.session.get(Active,line.id) or Active.query.filter_by(movement_id=movement.id).first():
        raise ValueError('Linha ou lançamento já conciliado.')
    row=Link(organization_code=org,account_id=account.id,line_id=line.id,movement_id=movement.id,
        idempotency_key=request['idempotency_key'],request_json=t.dump(request),
        snapshot_json=t.dump({'line':line.to_dict(),'movement':movement.to_dict(),'date_difference_reason':request['date_difference_reason']}),created_by=actor)
    db.session.add(row); db.session.flush()
    db.session.add(Active(line_id=line.id,movement_id=movement.id,reconciliation_id=row.id)); db.session.flush()
    return Result(True,data=link_detail(row),code=201)


@t.transaction
def undo_reconciliation(row_id,data,*,actor):
    actor=text(actor,120,'Autor')
    data=t.fields(data,{'reason','idempotency_key'})
    row=db.session.get(Link,t.ident(row_id))
    if row is None: raise ValueError('Conciliação não encontrada.')
    t.reserve(t.Account,row.account_id)
    request={**data,'reconciliation_id':row.id,'reason':text(data['reason'],1000,'Motivo'),'idempotency_key':text(data['idempotency_key'],80,'Chave')}
    old=replay(Undo,row.organization_code,request['idempotency_key'],request)
    if old: return Result(True,data=old.to_dict())
    resolve_organization_by_code(row.organization_code,require_active=True)
    active=db.session.get(Active,row.line_id)
    if not active or active.reconciliation_id!=row.id: raise ValueError('Conciliação já desfeita.')
    undo=Undo(organization_code=row.organization_code,reconciliation_id=row.id,idempotency_key=request['idempotency_key'],
        request_json=t.dump(request),reason=request['reason'],created_by=actor)
    db.session.add(undo); db.session.delete(active); db.session.flush()
    return Result(True,data=undo.to_dict(),code=201)
