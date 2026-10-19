"""Projeção atual pelo valor contábil congelado; realizado por data de operação."""
from datetime import timedelta
from collections import defaultdict
from decimal import Decimal, localcontext
from functools import wraps
from services.core.organization_service import resolve_organization_by_code
from ..model.monetary import MonetaryPolicy
from ..model.cash_operations import BankStatementLine as Line, ActiveBankReconciliation as Active, BankReconciliation as Link, BankReconciliationUndo as Undo
from . import treasury_service as t
from .exchange_service import day


def exact(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext() as context:
            context.prec=64
            return function(*args,**kwargs)
    return wrapped


def selection(options):
    options=t.fields(options,{'organization_code','date_from','date_to'},{'account_id'})
    org=resolve_organization_by_code(options['organization_code'],require_active=False)
    start,end=day(options['date_from']),day(options['date_to'])
    if end<start or (end-start).days>365: raise ValueError('Selecione intervalo de até 366 dias.')
    policy=MonetaryPolicy.query.filter_by(organization_code=org['code']).first()
    if policy is None: raise ValueError('Organização sem política monetária.')
    account_id=t.ident(options.get('account_id'),optional=True)
    if account_id:
        account=t.db.session.get(t.Account,account_id)
        if account is None or account.organization_code!=org['code']: raise ValueError('Conta de outra organização ou inexistente.')
    return org,start,end,account_id,policy.currency_code


def bounded(query,limit=10000):
    rows=query.limit(limit+1).all()
    if len(rows)>limit: raise ValueError('Consulta excede o limite; reduza o período ou selecione uma conta.')
    return rows


@exact
def cash_flow(options):
    org,start,end,account_id,currency=selection(options)
    query=t.Movement.query.join(t.Account).filter(t.Account.organization_code==org['code'],t.Movement.operation_date<=end)
    if account_id: query=query.filter(t.Movement.account_id==account_id)
    movements=bounded(query.order_by(t.Movement.operation_date,t.Movement.id))
    opening=sum((m.amount_delta for m in movements if m.operation_date<start),Decimal(0))
    dates={}
    for i in range((end-start).days+1):
        date=start+timedelta(days=i)
        dates[date]={'date':date.isoformat(), **{k:Decimal(0) for k in ('income','outflow','funding','internal_net','planned_income','planned_outflow','pending_income','pending_outflow')}}
    for movement in movements:
        if movement.operation_date<start: continue
        row=dates[movement.operation_date]; amount=movement.amount_delta
        if movement.reference.startswith(('transfer:','transfer-reversal:')): row['internal_net']+=amount
        elif movement.reference.startswith('opening:'): row['funding']+=amount
        elif amount>=0: row['income']+=amount
        else: row['outflow']-=amount
    overdue_income=overdue_outflow=Decimal(0)
    if not account_id:
        source=t.Title.query.filter_by(organization_code=org['code']).filter(t.Title.issue_date<=end)
        parts=t.Installment.query.join(t.Title).filter(t.Title.organization_code==org['code'],t.Title.issue_date<=end)
        if parts.limit(10001).count()>10000: raise ValueError('Projeção excede 10.000 parcelas; selecione uma conta para consultar somente o realizado.')
        titles=bounded(source)
        for title in titles:
            detail=t.title_detail(title.id)
            if detail['status']=='CANCELLED': continue
            side='income' if title.kind=='RECEIVABLE' else 'outflow'
            for part in detail['installments']:
                due=day(part['due_date'])
                if start<=due<=end:
                    dates[due]['planned_'+side]+=Decimal(part['base_amount'])
                    dates[due]['pending_'+side]+=Decimal(part['carrying_remaining'])
                elif due<start:
                    if side=='income': overdue_income+=Decimal(part['carrying_remaining'])
                    else: overdue_outflow+=Decimal(part['carrying_remaining'])
    actual=opening; projection=opening+overdue_income-overdue_outflow
    items=[]
    for row in dates.values():
        delta=row['income']-row['outflow']+row['funding']+row['internal_net']
        actual+=delta
        projection+=delta+row['pending_income']-row['pending_outflow']
        items.append({k:t.canonical(v) if isinstance(v,Decimal) else v for k,v in {**row,'realized_balance':actual,'projected_balance':projection}.items()})
    return {'contract':'financeiro.cash_flow.v1','organization_code':org['code'],'organization_name':org['name'],
        'currency_code':currency,'date_from':start.isoformat(),'date_to':end.isoformat(),'account_id':account_id,
        'opening_balance':t.canonical(opening),'closing_balance':t.canonical(actual),'projected_balance':t.canonical(projection),
        'overdue_income':t.canonical(overdue_income),'overdue_outflow':t.canonical(overdue_outflow),'forecast_available':account_id is None,
        'forecast_basis':'Saldo pendente atual no valor contábil congelado; não é posição histórica nem cotação futura. Vencidos anteriores ao período entram no saldo projetado inicial. Transferências internas não são receitas/despesas.',
        'items':items}


@exact
def reconciliation_data(options):
    org,start,end,account_id,currency=selection(options)
    query=Line.query.join(t.Account,Line.account_id==t.Account.id).filter(t.Account.organization_code==org['code'],Line.operation_date.between(start,end))
    if account_id: query=query.filter(Line.account_id==account_id)
    lines=bounded(query.order_by(Line.operation_date,Line.id))
    items=[]
    for line in lines:
        active=t.db.session.get(Active,line.id)
        items.append({**line.to_dict(),'status':'LINKED' if active else 'PENDING',
            'movement_id':active.movement_id if active else None,'reconciliation_id':active.reconciliation_id if active else None})
    movements=t.Movement.query.join(t.Account).outerjoin(Active,Active.movement_id==t.Movement.id).filter(
        t.Account.organization_code==org['code'],t.Movement.operation_date.between(start,end),Active.line_id.is_(None))
    if account_id: movements=movements.filter(t.Movement.account_id==account_id)
    unmatched=[row.to_dict() for row in bounded(movements.order_by(t.Movement.operation_date,t.Movement.id))]
    candidates=defaultdict(list)
    for movement in unmatched: candidates[(movement['account_id'],Decimal(movement['amount_delta']))].append(movement)
    for line in items:
        line['candidates']=candidates[(line['account_id'],Decimal(line['amount']))]
    history_query=Link.query.join(Line,Link.line_id==Line.id).filter(Link.organization_code==org['code'],Line.operation_date.between(start,end))
    if account_id: history_query=history_query.filter(Link.account_id==account_id)
    history=[]
    for link in bounded(history_query.order_by(Link.id.desc())):
        undo=Undo.query.filter_by(reconciliation_id=link.id).first()
        history.append({**link.to_dict(),'undo':undo.to_dict() if undo else None})
    return {'contract':'financeiro.reconciliation.v1','organization_code':org['code'],'organization_name':org['name'],
        'currency_code':currency,'date_from':start.isoformat(),'date_to':end.isoformat(),'items':items,'unmatched_movements':unmatched,'history':history,
        'pending_count':sum(i['status']=='PENDING' for i in items),'linked_count':sum(i['status']=='LINKED' for i in items)}


@exact
def report_data(kind,options):
    """Contrato público somente DTOs, strings monetárias e limites explícitos."""
    if kind in ('dre','results_dashboard'):
        from .accrual_service import statement
        if kind=='results_dashboard':
            from .result_dashboard_service import dashboard
            value=dashboard(options)
        else:value=statement(options)
        if len(value['items'])>2000:raise ValueError('Relatório excede 2000 linhas.')
        return value
    org,start,end,account_id,currency=selection(options)
    if kind=='cash_flow': value=cash_flow(options)
    elif kind=='reconciliation': value=reconciliation_data(options)
    elif kind=='titles':
        if account_id: raise ValueError('Títulos pendentes não possuem conta financeira atribuída.')
        items=[t.title_detail(row.id) for row in bounded(t.Title.query.filter_by(organization_code=org['code']).filter(t.Title.issue_date.between(start,end)),2000)]
        value={'contract':'financeiro.titles.v1','items':items}
    elif kind=='settlements':
        query=t.Settlement.query.filter_by(organization_code=org['code']).filter(t.Settlement.operation_date.between(start,end))
        if account_id: query=query.filter_by(account_id=account_id)
        items=[t.settlement_detail(row) for row in bounded(query,2000)]
        for item in items: item['currency_code']=item['snapshot']['currency_code']
        value={'contract':'financeiro.settlements.v1','items':items}
    else: raise ValueError('Relatório financeiro desconhecido.')
    if len(value['items'])>2000 or len(value.get('unmatched_movements',[]))>2000: raise ValueError('Relatório excede 2000 linhas.')
    return {**value,'organization_code':org['code'],'organization_name':org['name'],'currency_code':currency,
        'date_from':start.isoformat(),'date_to':end.isoformat()}
