"""Dashboard operacional: valores exatos, pendências atuais e trilhas navegáveis."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from . import treasury_service as t, cash_flow_service as f
from ..model.cash_operations import BankStatementLine as Line, ActiveBankReconciliation as Active


@f.exact
def dashboard(options):
    org,start,end,account_id,currency=f.selection(options)
    if account_id: raise ValueError('Dashboard consolidado exige todas as contas da organização.')
    cash=f.cash_flow(options)
    parts=t.Installment.query.join(t.Title).filter(t.Title.organization_code==org['code'])
    if parts.limit(10001).count()>10000: raise ValueError('Dashboard excede 10.000 parcelas; consulte os títulos com filtros.')
    titles=f.bounded(t.Title.query.filter_by(organization_code=org['code']))
    pending={'PAYABLE':Decimal(0),'RECEIVABLE':Decimal(0)}
    overdue={'PAYABLE':Decimal(0),'RECEIVABLE':Decimal(0)}
    agenda=[]; windows={str(days):{'PAYABLE':Decimal(0),'RECEIVABLE':Decimal(0)} for days in (7,15,30)}
    for title in titles:
        detail=t.title_detail(title.id)
        if detail['status']=='CANCELLED': continue
        for part in detail['installments']:
            remaining=Decimal(part['carrying_remaining'])
            if remaining<=0: continue
            due=f.day(part['due_date']); pending[title.kind]+=remaining
            if due<end: overdue[title.kind]+=remaining
            for days in (7,15,30):
                if end<=due<end+timedelta(days=days): windows[str(days)][title.kind]+=remaining
            if due<end+timedelta(days=30):
                agenda.append({'title_id':title.id,'reference':title.reference,'counterparty':title.counterparty,'kind':title.kind,
                    'installment':part['number'],'due_date':part['due_date'],'base_remaining':t.canonical(remaining),
                    'original_remaining':part['remaining'],'currency_code':title.currency_code})
    accounts=[]
    movements=f.bounded(t.Movement.query.join(t.Account).filter(t.Account.organization_code==org['code'],t.Movement.operation_date<=end))
    balance=defaultdict(lambda:Decimal(0))
    for movement in movements: balance[movement.account_id]+=movement.amount_delta
    for account in f.bounded(t.Account.query.filter_by(organization_code=org['code']).order_by(t.Account.name)):
        accounts.append({'id':account.id,'name':account.name,'is_active':account.is_active,'currency_code':account.currency_code,
            'balance':t.canonical(balance[account.id])})
    categories=defaultdict(lambda:Decimal(0)); centers=defaultdict(lambda:Decimal(0)); monthly=defaultdict(lambda:{'income':Decimal(0),'outflow':Decimal(0)})
    for movement in movements:
        if not start<=movement.operation_date<=end or movement.reference.startswith(('opening:','transfer:','transfer-reversal:')): continue
        month=movement.operation_date.strftime('%Y-%m'); delta=movement.amount_delta
        monthly[month]['income' if delta>=0 else 'outflow']+=abs(delta)
        snapshot=movement.to_dict()['snapshot']
        if delta<0 or movement.reference.startswith('reversal:'):
            original=snapshot.get('original_movement',{}).get('snapshot',snapshot)
            if original.get('kind')=='PAYABLE':
                category=original.get('category',{}); center=original.get('cost_center',{})
                categories[(category.get('id'),category.get('name','Sem categoria'))]-=delta
                centers[(center.get('id'),center.get('name','Sem centro'))]-=delta
    lines=f.bounded(Line.query.join(t.Account,Line.account_id==t.Account.id).filter(t.Account.organization_code==org['code'],Line.operation_date.between(start,end)))
    line_pending=sum(t.db.session.get(Active,row.id) is None for row in lines)
    unmatched=t.Movement.query.join(t.Account).outerjoin(Active,Active.movement_id==t.Movement.id).filter(
        t.Account.organization_code==org['code'],t.Movement.operation_date.between(start,end),Active.line_id.is_(None)).count()
    def strings(values): return {k:t.canonical(v) for k,v in values.items()}
    income=sum((Decimal(row['income']) for row in cash['items']),Decimal(0))
    outflow=sum((Decimal(row['outflow']) for row in cash['items']),Decimal(0))
    return {'organization_code':org['code'],'organization_name':org['name'],'currency_code':currency,
        'date_from':start.isoformat(),'date_to':end.isoformat(),'pending':strings(pending),'overdue':strings(overdue),
        'income':t.canonical(income),'outflow':t.canonical(outflow),'net':t.canonical(income-outflow),
        'balance':cash['closing_balance'],'minimum_projected_balance':t.canonical(min(Decimal(row['projected_balance']) for row in cash['items'])),
        'cash':cash,'accounts':accounts,'agenda':sorted(agenda,key=lambda row:(row['due_date'],row['title_id'],row['installment'])),
        'windows':{key:strings(value) for key,value in windows.items()},'pending_lines':line_pending,'unmatched_movements':unmatched,
        'categories':[{'id':key[0],'name':key[1],'amount':t.canonical(value)} for key,value in sorted(categories.items(),key=lambda pair:pair[0][1])],
        'centers':[{'id':key[0],'name':key[1],'amount':t.canonical(value)} for key,value in sorted(centers.items(),key=lambda pair:pair[0][1])],
        'monthly':[{'month':month,**strings(value)} for month,value in sorted(monthly.items())]}
