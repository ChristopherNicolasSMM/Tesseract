"""Competência gerencial explícita; reconhecimento não movimenta caixa/estoque."""
import calendar
import json
import re
from datetime import date
from decimal import Decimal, localcontext
from core.db import db
from services.core.organization_service import Result, resolve_organization_by_code
from ..model.accrual import ResultClassification as Classification, AccrualEntry as Entry, AccrualAllocation as Allocation, AccrualReversal as Reversal, ActiveAccrual as Active
from . import treasury_service as t, cash_flow_service as f
from .exchange_service import text,day
from .policy_version_service import resolve_selected_policy

GROUPS={
 'REVENUE':('Receita bruta',1),'DEDUCTIONS':('Deduções da receita',-1),
 'COST':('Custos reconhecidos',-1),'OPERATING_EXPENSE':('Despesas operacionais',-1),
 'FINANCIAL_INCOME':('Receitas financeiras',1),'FINANCIAL_EXPENSE':('Despesas financeiras',-1),
 'INCOME_TAX':('Tributos sobre o lucro',-1),'NON_RESULT':('Não afeta o resultado',0)}
COMPONENTS=('INTEREST','FINE','DISCOUNT','FX','ROUNDING')


def period(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}',value):raise ValueError('Competência: use AAAA-MM.')
    return day(value+'-01')


def replay(model,org,key,request):
    row=model.query.filter_by(organization_code=org,idempotency_key=key).first()
    if row and row.request_json!=t.dump(request):raise ValueError('Chave já utilizada com outro conteúdo.')
    return row


def entry_detail(row):
    reverse=Reversal.query.filter_by(entry_id=row.id).first()
    return {**row.to_dict(),'allocations':[a.to_dict() for a in Allocation.query.filter_by(entry_id=row.id).order_by(Allocation.id)],
        'status':'REVERSED' if reverse else 'RECOGNIZED','reversal':reverse.to_dict() if reverse else None}


@t.transaction
def classify(data,*,actor):
    actor=text(actor,120,'Autor')
    data=t.fields(data,{'organization_code','category_id','expected_version','group_code','valid_from','reason','idempotency_key'})
    org=resolve_organization_by_code(data['organization_code'],require_active=False)['code']
    if not isinstance(data['group_code'],str) or data['group_code'] not in GROUPS:raise ValueError('Grupo de resultado inválido.')
    if type(data['expected_version']) is not int or not 0<=data['expected_version']<1000000:raise ValueError('Versão esperada inválida.')
    request={**data,'organization_code':org,'category_id':t.ident(data['category_id']),
        'reason':text(data['reason'],1000,'Motivo'),'idempotency_key':text(data['idempotency_key'],80,'Chave')}
    valid=day(data['valid_from'])
    if valid.day!=1:raise ValueError('Vigência de classificação deve iniciar no primeiro dia do mês.')
    old=replay(Classification,org,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    resolve_organization_by_code(org,require_active=True)
    category=t.catalog_row(t.Category,request['category_id'],org)
    old=replay(Classification,org,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    last=Classification.query.filter_by(category_id=category.id).order_by(Classification.version.desc()).first()
    version=last.version if last else 0
    if version!=data['expected_version']:raise ValueError('Classificação mudou; atualize a versão esperada.')
    if last and valid<last.valid_from:raise ValueError('Nova vigência anterior à versão existente.')
    allowed=('REVENUE','FINANCIAL_INCOME','NON_RESULT') if category.direction=='RECEIVABLE' else ('DEDUCTIONS','COST','OPERATING_EXPENSE','FINANCIAL_EXPENSE','INCOME_TAX','NON_RESULT')
    if data['group_code'] not in allowed:raise ValueError('Grupo incompatível com a finalidade pagar/receber da categoria.')
    row=Classification(organization_code=org,category_id=category.id,version=version+1,group_code=data['group_code'],valid_from=valid,
        reason=request['reason'],idempotency_key=request['idempotency_key'],request_json=t.dump(request),
        snapshot_json=t.dump({'category':category.to_dict(),'group_label':GROUPS[data['group_code']][0]}),created_by=actor)
    db.session.add(row);db.session.flush()
    return Result(True,data=row.to_dict(),code=201)


def settlement_components(row):
    snapshot=json.loads(row.snapshot_json); values={}
    payable=snapshot['kind']=='PAYABLE'
    for component in COMPONENTS:
        value=Decimal(snapshot['exchange_difference'] if component=='FX' else snapshot['rounding_difference'] if component=='ROUNDING' else snapshot['conversions'][component.lower()]['converted_amount'])
        if not value:continue
        income=(not payable) if component in ('INTEREST','FINE') else payable if component=='DISCOUNT' else ((not payable) if value>0 else payable)
        values[component]={'amount':abs(value),'group_code':'FINANCIAL_INCOME' if income else 'FINANCIAL_EXPENSE'}
    return values


def parent_id(source_type,source_id):
    if source_type=='TITLE':return source_id
    if source_type=='SETTLEMENT':
        row=db.session.get(t.Settlement,source_id)
        if row:return db.session.get(t.Installment,row.installment_id).title_id
        raise ValueError('Baixa não encontrada.')
    return None


def normalize(data):
    data=t.fields(data,{'organization_code','source_type','source_id','component','reference','classification_id','effect','amount','currency_code','policy_version_id','reason','idempotency_key','allocations'})
    if data['source_type'] not in ('TITLE','SETTLEMENT','ADJUSTMENT'):raise ValueError('Origem inválida.')
    if data['effect'] not in ('RECOGNIZE','REDUCE'):raise ValueError('Efeito inválido.')
    org=resolve_organization_by_code(data['organization_code'],require_active=False)['code']
    t.ident(data['policy_version_id'],optional=True)
    if data['source_type']=='ADJUSTMENT':
        if data['source_id'] is not None or data['component'] is not None:raise ValueError('Ajuste manual não possui ID de título/baixa ou componente.')
    else:
        t.ident(data['source_id'])
        if data['effect']!='RECOGNIZE' or data['policy_version_id'] is not None:raise ValueError('Origem registrada não admite redução ou nova política; estorne e reapresente.')
        if data['source_type']=='TITLE' and data['component'] is not None or data['source_type']=='SETTLEMENT' and data['component'] not in COMPONENTS:raise ValueError('Componente inválido para a origem.')
    request={**data,'organization_code':org,'classification_id':t.ident(data['classification_id']),
        'amount':t.canonical(t.amount(data['amount'])),'reference':text(data['reference'],120,'Referência'),
        'reason':text(data['reason'],1000,'Motivo'),'idempotency_key':text(data['idempotency_key'],80,'Chave')}
    if not isinstance(data['allocations'],list) or not 1<=len(data['allocations'])<=120:raise ValueError('Informe de 1 a 120 apropriações explícitas.')
    lines=[];seen=set()
    for line in data['allocations']:
        line=t.fields(line,{'period','cost_center_id','amount'})
        month=period(line['period']);center=t.ident(line['cost_center_id'])
        if (month,center) in seen:raise ValueError('Competência/centro repetidos; consolide a linha.')
        seen.add((month,center))
        lines.append({'period':month.strftime('%Y-%m'),'cost_center_id':center,'amount':t.canonical(t.amount(line['amount']))})
    request['allocations']=sorted(lines,key=lambda line:(line['period'],line['cost_center_id']))
    return request


@t.transaction
def recognize(data,*,actor,preview=False):
    actor=text(actor,120,'Autor');request=normalize(data);org=request['organization_code']
    old=replay(Entry,org,request['idempotency_key'],request)
    if old:return Result(True,data=entry_detail(old))
    resolve_organization_by_code(org,require_active=True)
    title_id=parent_id(request['source_type'],request['source_id'])
    title=None
    if title_id:
        title=t.reserve(t.Title,title_id) if not preview else db.session.get(t.Title,title_id)
        if not title or title.organization_code!=org:raise ValueError('Título de outra organização ou inexistente.')
        if db.session.get(t.Cancellation,title_id):raise ValueError('Título cancelado não pode ser reconhecido.')
    classification=db.session.get(Classification,request['classification_id'])
    if classification is None or classification.organization_code!=org:raise ValueError('Classificação inexistente ou de outra organização.')
    category=t.catalog_row(t.Category,classification.category_id,org,lock=not preview)
    old=replay(Entry,org,request['idempotency_key'],request)
    if old:return Result(True,data=entry_detail(old))
    source={};group=classification.group_code
    if request['source_type']=='TITLE':
        if classification.category_id!=title.category_id:raise ValueError('Classificação deve pertencer à categoria do título.')
        if title.source_reference and title.source_reference.startswith('purchase:') and group!='NON_RESULT':
            raise ValueError('Compra de estoque exige exclusão patrimonial; custo reconhecido será apropriado separadamente, sem duplicar a compra.')
        source_key=f'title:{title.id}';value=title.base_amount
        snapshot=json.loads(title.snapshot_json);policy=snapshot['conversion']['policy']
        source={'title_id':title.id,'reference':title.reference,'original_amount':t.canonical(title.amount),'original_currency':title.currency_code,'valuation':snapshot['conversion'],'source_reference':title.source_reference}
    elif request['source_type']=='SETTLEMENT':
        row=db.session.get(t.Settlement,request['source_id'])
        if t.Reversal.query.filter_by(settlement_id=row.id).first():raise ValueError('Baixa estornada não pode ser apropriada.')
        values=settlement_components(row);component=request['component']
        if component not in values:raise ValueError('Componente é zero ou ausente.')
        if group!=values[component]['group_code']:raise ValueError('Componente exige grupo financeiro de receita/despesa compatível.')
        value=values[component]['amount'];source_key=f'settlement:{row.id}:{component}'
        snapshot=json.loads(row.snapshot_json);policy=snapshot['conversions']['cash']['policy']
        source={'title_id':title.id,'settlement_id':row.id,'component':component,'settlement_snapshot':snapshot}
    else:
        source_key='adjustment:'+request['reference'];value=t.amount(request['amount'],positive=True)
        policy=resolve_selected_policy(org,policy_version_id=request['policy_version_id'],operation_date=request['allocations'][0]['period']+'-01')
        source={'manual_adjustment':True,'reference':request['reference']}
    if Active.query.filter_by(organization_code=org,source_key=source_key).first():raise ValueError('Origem já apropriada. Estorne o reconhecimento antes de reapresentar.')
    if request['currency_code']!=policy['currency_code']:raise ValueError('Informe explicitamente a moeda base da avaliação de origem.')
    if Decimal(request['amount'])!=value:raise ValueError('Total difere do valor base congelado da origem.')
    total=Decimal(0);allocations=[]
    centers={center_id:t.catalog_row(t.Center,center_id,org,lock=not preview) for center_id in sorted({line['cost_center_id'] for line in request['allocations']})}
    for line in request['allocations']:
        month=period(line['period'])
        if month<classification.valid_from.replace(day=1):raise ValueError('Competência anterior à vigência da classificação.')
        amount=t.amount(line['amount'],scale=policy['decimal_places'])
        if amount<=0 and value!=0:raise ValueError('Cada apropriação deve ser positiva.')
        total+=amount
        allocations.append({**line,'snapshot':{'cost_center':centers[line['cost_center_id']].to_dict()}})
    if total!=value:raise ValueError('Apropriações devem conservar exatamente o total base; ajuste explicitamente o resíduo.')
    frozen={'source':source,'classification':classification.to_dict(),'category':category.to_dict(),'policy':policy,'allocations':allocations}
    result={**request,'source_key':source_key,'snapshot':frozen}
    if preview:return Result(True,data=result)
    row=Entry(organization_code=org,source_key=source_key,source_type=request['source_type'],source_id=request['source_id'],component=request['component'],
        reference=request['reference'],classification_id=classification.id,effect=request['effect'],amount=value,currency_code=request['currency_code'],reason=request['reason'],
        idempotency_key=request['idempotency_key'],request_json=t.dump(request),snapshot_json=t.dump(frozen),created_by=actor)
    db.session.add(row);db.session.flush()
    for line in allocations:db.session.add(Allocation(entry_id=row.id,period=period(line['period']),cost_center_id=line['cost_center_id'],amount=Decimal(line['amount']),snapshot_json=t.dump(line['snapshot']),created_by=actor))
    db.session.add(Active(organization_code=org,source_key=source_key,entry_id=row.id));db.session.flush()
    return Result(True,data=entry_detail(row),code=201)


def preview(data,*,actor):
    try:
        with db.session.no_autoflush,localcontext() as ctx:
            ctx.prec=64
            return recognize.__wrapped__(data,actor=actor,preview=True)
    except ValueError as exc:return Result(False,error=str(exc),code=422)


@t.transaction
def reverse(entry_id,data,*,actor):
    actor=text(actor,120,'Autor');data=t.fields(data,{'reason','idempotency_key'})
    row=db.session.get(Entry,t.ident(entry_id))
    if not row:raise ValueError('Reconhecimento não encontrado.')
    request={'entry_id':row.id,'reason':text(data['reason'],1000,'Motivo'),'idempotency_key':text(data['idempotency_key'],80,'Chave')}
    old=replay(Reversal,row.organization_code,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    resolve_organization_by_code(row.organization_code,require_active=True)
    parent=parent_id(row.source_type,row.source_id)
    if parent:t.reserve(t.Title,parent)
    t.reserve(t.Category,db.session.get(Classification,row.classification_id).category_id)
    row=t.reserve(Entry,row.id)
    old=replay(Reversal,row.organization_code,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    active=Active.query.filter_by(entry_id=row.id).first()
    if active is None:raise ValueError('Reconhecimento já estornado.')
    reversal=Reversal(organization_code=row.organization_code,entry_id=row.id,reason=request['reason'],idempotency_key=request['idempotency_key'],request_json=t.dump(request),created_by=actor)
    db.session.add(reversal);db.session.delete(active);db.session.flush()
    return Result(True,data=reversal.to_dict(),code=201)


def assert_source_unrecognized(source_key,*,prefix=False):
    query=Active.query.filter(Active.source_key.like(source_key+'%')) if prefix else Active.query.filter_by(source_key=source_key)
    if query.first():raise ValueError('Estorne primeiro o reconhecimento de competência/DRE vinculado a esta origem.')


@f.exact
def review(organization_code):
    org=resolve_organization_by_code(organization_code,require_active=False)['code']
    active={row.source_key for row in f.bounded(Active.query.filter_by(organization_code=org))}
    categories={row.id:row for row in f.bounded(t.Category.query.filter_by(organization_code=org))}
    latest={}
    for row in f.bounded(Classification.query.filter_by(organization_code=org).order_by(Classification.version)):
        latest[row.category_id]=row.to_dict()
    titles=f.bounded(t.Title.query.filter_by(organization_code=org),2000)
    cancelled={row.title_id for row in t.Cancellation.query.filter(t.Cancellation.title_id.in_([title.id for title in titles])).all()}
    pending=[]
    for title in titles:
        key=f'title:{title.id}'
        if title.id in cancelled or key in active:continue
        category=categories[title.category_id]
        pending.append({'source_type':'TITLE','source_id':title.id,'component':None,'source_key':key,'reference':title.reference,
            'amount':t.canonical(title.base_amount),'currency_code':json.loads(title.snapshot_json)['conversion']['target_currency'],
            'category_id':category.id,'category_name':category.name,'classification':latest.get(category.id),
            'purchase_stock':bool(title.source_reference and title.source_reference.startswith('purchase:')),
            'status':'NEEDS_RECOGNITION' if category.id in latest else 'NEEDS_CLASSIFICATION'})
    settlements=f.bounded(t.Settlement.query.filter_by(organization_code=org),2000)
    reversed_ids={row.settlement_id for row in t.Reversal.query.filter(t.Reversal.settlement_id.in_([row.id for row in settlements])).all()}
    for row in settlements:
        if row.id in reversed_ids:continue
        snapshot=json.loads(row.snapshot_json)
        for component,value in settlement_components(row).items():
            key=f'settlement:{row.id}:{component}'
            if key in active:continue
            pending.append({'source_type':'SETTLEMENT','source_id':row.id,'component':component,'source_key':key,
                'reference':f'Baixa {row.id} / {component}','amount':t.canonical(value['amount']),'currency_code':snapshot['base_currency'],
                'category_id':None,'category_name':'Classificação financeira explícita','classification':None,'required_group':value['group_code'],
                'purchase_stock':False,'status':'NEEDS_FINANCIAL_CLASSIFICATION'})
    if len(pending)>2000:raise ValueError('Revisão excede 2000 origens; regularize as pendências antes de ampliar a consulta.')
    return {'items':pending,'count':len(pending),'classifications':list(latest.values())}


@f.exact
def statement(options):
    options=t.fields(options,{'organization_code','date_from','date_to'},{'cost_center_id','group_code'})
    org,start,end,_,currency=f.selection({k:options[k] for k in ('organization_code','date_from','date_to')})
    center_id=t.ident(options.get('cost_center_id'),optional=True)
    if center_id:
        center=db.session.get(t.Center,center_id)
        if not center or center.organization_code!=org['code']:raise ValueError('Centro de custo de outra organização ou inexistente.')
    group_filter=options.get('group_code')
    if group_filter is not None and (not isinstance(group_filter,str) or group_filter not in GROUPS):raise ValueError('Grupo inválido.')
    start=start.replace(day=1);end=end.replace(day=calendar.monthrange(end.year,end.month)[1])
    months=[];cursor=start
    while cursor<=end:
        months.append(cursor.strftime('%Y-%m'))
        if cursor.year==end.year and cursor.month==end.month:break
        cursor=date(cursor.year+1,1,1) if cursor.month==12 else date(cursor.year,cursor.month+1,1)
    query=Allocation.query.join(Entry,Allocation.entry_id==Entry.id).join(Active,Active.entry_id==Entry.id).filter(Entry.organization_code==org['code'],Allocation.period.between(start,end))
    if center_id:query=query.filter(Allocation.cost_center_id==center_id)
    allocations=f.bounded(query.order_by(Allocation.period,Allocation.id))
    values={code:{month:Decimal(0) for month in months} for code in GROUPS}
    details=[];cache={}
    for allocation in allocations:
        row=cache.setdefault(allocation.entry_id,db.session.get(Entry,allocation.entry_id))
        frozen=json.loads(row.snapshot_json);classification=frozen['classification'];code=classification['group_code']
        effect=-1 if row.effect=='REDUCE' else 1
        value=allocation.amount*GROUPS[code][1]*effect
        month=allocation.period.strftime('%Y-%m');values[code][month]+=value
        if group_filter is None or code==group_filter:
            details.append({'entry_id':row.id,'period':month,'source_key':row.source_key,'source_type':row.source_type,
                'reference':row.reference,'group_code':code,'group_label':GROUPS[code][0],'effect':row.effect,
                'amount':t.canonical(allocation.amount),'result_amount':t.canonical(value),'currency_code':row.currency_code,
                'cost_center_id':allocation.cost_center_id,'cost_center_name':json.loads(allocation.snapshot_json)['cost_center']['name'],
                'classification_version':classification['version'],'category_name':frozen['category']['name'],'created_by':row.created_by,'reason':row.reason})
    lines=[];export=[]
    def add(code,label,components=None):
        current=values[code] if components is None else {month:sum((values[group][month] for group in components),Decimal(0)) for month in months}
        item={'code':code,'label':label,'subtotal':components is not None,'values':{month:t.canonical(value) for month,value in current.items()},'total':t.canonical(sum(current.values(),Decimal(0)))}
        lines.append(item)
        export.extend({'period':month,'label':label,'amount':t.canonical(value)} for month,value in current.items())
    add('REVENUE',GROUPS['REVENUE'][0]);add('DEDUCTIONS',GROUPS['DEDUCTIONS'][0]);add('NET_REVENUE','Receita líquida',('REVENUE','DEDUCTIONS'))
    add('COST',GROUPS['COST'][0]);add('GROSS_RESULT','Resultado bruto',('REVENUE','DEDUCTIONS','COST'))
    add('OPERATING_EXPENSE',GROUPS['OPERATING_EXPENSE'][0]);base=('REVENUE','DEDUCTIONS','COST','OPERATING_EXPENSE')
    add('OPERATING_RESULT','Resultado operacional',base)
    add('FINANCIAL_INCOME',GROUPS['FINANCIAL_INCOME'][0]);add('FINANCIAL_EXPENSE',GROUPS['FINANCIAL_EXPENSE'][0])
    base+=('FINANCIAL_INCOME','FINANCIAL_EXPENSE');add('BEFORE_TAX','Resultado antes dos tributos sobre o lucro',base)
    add('INCOME_TAX',GROUPS['INCOME_TAX'][0]);add('NET_RESULT','Resultado líquido gerencial parcial',base+('INCOME_TAX',))
    add('NON_RESULT','Exclusões patrimoniais (efeito zero)')
    pending=review(org['code'])
    return {'contract':'financeiro.dre.v1','organization_code':org['code'],'organization_name':org['name'],'currency_code':currency,
        'date_from':start.isoformat(),'date_to':end.isoformat(),'months':months,'rows':lines,'items':export,'details':details,
        'pending_count':pending['count'],'status':'PARTIAL','status_label':'DRE gerencial parcial',
        'basis':'Competências mensais integrais. Estado atual dos reconhecimentos; estornos reapresentam a competência original. Integração automática de custos e fechamento ainda não disponíveis. Pendências abrangem o cadastro atual da organização.',
        'cost_center_id':center_id,'group_code':group_filter}
