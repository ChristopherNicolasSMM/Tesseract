"""Conferência, bloqueio de competências e reabertura com snapshot auditável."""
import calendar
import hashlib
from datetime import date
from core.db import db
from services.core.organization_service import Result,resolve_organization_by_code
from ..model.monetary import MonetaryPolicy
from ..model.result_close import ResultClose as Close,ResultReopen as Reopen,ActiveResultClose as ActiveClose
from . import treasury_service as t,accrual_service as a

ATTESTATIONS={'revenue_complete','costs_complete','taxes_reviewed','adjustments_reviewed'}


def lock_organization(org):
    policy=MonetaryPolicy.query.filter_by(organization_code=org).first()
    if not policy:raise ValueError('Organização sem política monetária.')
    return t.reserve(MonetaryPolicy,policy.id)


def assert_open(org,periods):
    if ActiveClose.query.filter(ActiveClose.organization_code==org,ActiveClose.period.in_(list(periods))).first():
        raise ValueError('Competência fechada; reabra explicitamente antes de reconhecer ou estornar valores.')


def close_detail(row):
    reopened=Reopen.query.filter_by(close_id=row.id).first()
    return {**row.to_dict(),'status':'REOPENED' if reopened else 'CLOSED','reopening':reopened.to_dict() if reopened else None}


def statuses(org,months):
    rows=ActiveClose.query.filter(ActiveClose.organization_code==org,ActiveClose.period.in_([a.period(month) for month in months])).all()
    return {row.period.strftime('%Y-%m'):{'id':row.close_id,'version':db.session.get(Close,row.close_id).version,'digest':db.session.get(Close,row.close_id).digest} for row in rows}


def conference(org,month):
    start=a.period(month);end=start.replace(day=calendar.monthrange(start.year,start.month)[1])
    review=a.review(org)
    pending=[item for item in review['items'] if not item.get('source_date') or a.day(item['source_date'])<=end]
    from .result_cost_contract import sources
    costs=sources(org)
    return {'period':month,'pending':pending,'pending_count':len(pending),'cost_source_available':costs['available'],
        'basis':'Conferência abrange origens pendentes com data até o fim da competência, inclusive anteriores. Cobertura econômica exige declaração administrativa explícita.'}


@t.transaction
def close(data,*,actor):
    actor=a.text(actor,120,'Autor')
    data=t.fields(data,{'organization_code','period','reason','idempotency_key','attestations'})
    org=resolve_organization_by_code(data['organization_code'],require_active=False)['code'];month=a.period(data['period'])
    attest=t.fields(data['attestations'],ATTESTATIONS)
    if any(value is not True for value in attest.values()):raise ValueError('Confirme explicitamente todas as declarações de cobertura.')
    request={**data,'organization_code':org,'reason':a.text(data['reason'],1000,'Motivo'),'idempotency_key':a.text(data['idempotency_key'],80,'Chave')}
    old=a.replay(Close,org,request['idempotency_key'],request)
    if old:return Result(True,data=close_detail(old))
    resolve_organization_by_code(org,require_active=True);lock_organization(org)
    old=a.replay(Close,org,request['idempotency_key'],request)
    if old:return Result(True,data=close_detail(old))
    if ActiveClose.query.filter_by(organization_code=org,period=month).first():raise ValueError('Competência já fechada.')
    checked=conference(org,data['period'])
    if checked['pending_count']:raise ValueError('Existem origens pendentes até a competência; revise e aproprie/exclua antes do fechamento.')
    statement=a.statement({'organization_code':org,'date_from':month.isoformat(),'date_to':month.replace(day=calendar.monthrange(month.year,month.month)[1]).isoformat()})
    last=Close.query.filter_by(organization_code=org,period=month).order_by(Close.version.desc()).first()
    statement={**statement,'status':'CLOSED_MANAGERIAL','status_label':'Fechamento gerencial com cobertura declarada'}
    frozen={'statement':statement,'conference':checked,'attestations':attest,'basis':'Fechamento gerencial com cobertura declarada; não substitui escrituração ou revisão contábil.'}
    digest=hashlib.sha256(t.dump(frozen).encode('utf-8')).hexdigest()
    row=Close(organization_code=org,period=month,version=last.version+1 if last else 1,reason=request['reason'],idempotency_key=request['idempotency_key'],
        request_json=t.dump(request),snapshot_json=t.dump(frozen),digest=digest,created_by=actor)
    db.session.add(row);db.session.flush();db.session.add(ActiveClose(organization_code=org,period=month,close_id=row.id));db.session.flush()
    return Result(True,data=close_detail(row),code=201)


@t.transaction
def reopen(close_id,data,*,actor):
    actor=a.text(actor,120,'Autor');data=t.fields(data,{'reason','idempotency_key'})
    row=db.session.get(Close,t.ident(close_id))
    if not row:raise ValueError('Fechamento não encontrado.')
    request={**data,'close_id':row.id,'reason':a.text(data['reason'],1000,'Motivo'),'idempotency_key':a.text(data['idempotency_key'],80,'Chave')}
    old=a.replay(Reopen,row.organization_code,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    resolve_organization_by_code(row.organization_code,require_active=True);lock_organization(row.organization_code)
    old=a.replay(Reopen,row.organization_code,request['idempotency_key'],request)
    if old:return Result(True,data=old.to_dict())
    active=ActiveClose.query.filter_by(close_id=row.id).first()
    if not active:raise ValueError('Fechamento já reaberto.')
    event=Reopen(organization_code=row.organization_code,close_id=row.id,reason=request['reason'],idempotency_key=request['idempotency_key'],request_json=t.dump(request),created_by=actor)
    db.session.add(event);db.session.delete(active);db.session.flush()
    return Result(True,data=event.to_dict(),code=201)
