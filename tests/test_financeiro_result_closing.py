"""Dashboard, custos e fechamento: cobertura explícita e competências bloqueadas."""
from decimal import Decimal
import pytest
from tests.test_financeiro_accrual import app,client,setup,title,ok,request,classification,options,_login_admin
from addons.addon_financeiro.root.services import accrual_service as a,treasury_service as t,result_closing_service as c,result_dashboard_service as dashboard
from core.db import db


def closing(**extra):return {'organization_code':'A','period':'2026-10','reason':'Conferência com evidências','idempotency_key':'CLOSE1',
    'attestations':{key:True for key in c.ATTESTATIONS},**extra}


def recognized(data,group='OPERATING_EXPENSE',kind='PAYABLE',total='100',key='TITLE',period='2026-10'):
    cat=data[2] if kind=='RECEIVABLE' else data[1]
    latest=a.Classification.query.filter_by(organization_code='A',category_id=cat['id']).order_by(a.Classification.version.desc()).first()
    classification_row=ok(a.classify(classification(data,group=group,category=cat,version=latest.version if latest else 0,key='CAT-'+key,valid_from='2026-09-01'),actor='admin'))
    source=ok(t.create_title(title(data,kind=kind,total=total,key=key),actor='admin'))
    payload=request(data,classification_row,source,idempotency_key='E-'+key,allocations=[{'period':period,'cost_center_id':data[3]['id'],'amount':source['base_amount']}])
    entry=ok(a.recognize(payload,actor='admin'))
    return source,classification_row,payload,entry


def test_closing_blocks_new_recognition_and_reversal_reopen_preserves_snapshots(app):
    with app.app_context():
        data=setup();source,cat,payload,entry=recognized(data)
        closed=ok(c.close(closing(),actor='admin'))
        assert closed['status']=='CLOSED' and len(closed['digest'])==64
        assert c.close(closing(),actor='admin').code==200
        assert c.close(closing(idempotency_key='OTHER'),actor='admin').code==422
        assert a.statement(options(date_to='2026-10-31'))['status']=='CLOSED_MANAGERIAL'
        assert a.reverse(entry['id'],{'reason':'Corrigir','idempotency_key':'R1'},actor='admin').code==422
        new=ok(t.create_title(title(data,key='LATE'),actor='admin'))
        assert a.statement(options(date_to='2026-10-31'))['status']=='CLOSED_WITH_PENDING'
        assert a.recognize(request(data,cat,new,idempotency_key='LATE'),actor='admin').code==422
        assert a.preview(request(data,cat,new,idempotency_key='LATE'),actor='admin').code==422
        opening={'reason':'Revisar origem retroativa','idempotency_key':'OPEN1'}
        ok(c.reopen(closed['id'],opening,actor='admin'))
        assert c.reopen(closed['id'],opening,actor='admin').code==200
        ok(a.recognize(request(data,cat,new,idempotency_key='LATE'),actor='admin'))
        second=ok(c.close(closing(idempotency_key='CLOSE2'),actor='admin'))
        assert second['version']==2
        assert c.reopen(closed['id'],opening,actor='admin').code==200
        assert c.ActiveClose.query.one().close_id==second['id']
        original=db.session.get(c.Close,closed['id']).to_dict()
        assert original['digest']==closed['digest'] and original['snapshot']==closed['snapshot']
        assert c.close(closing(),actor='admin').data['status']=='REOPENED'


def test_conference_requires_coverage_and_old_pending_but_not_future_origins(app):
    with app.app_context():
        data=setup();source,cat,payload,entry=recognized(data)
        incomplete=closing(attestations={**closing()['attestations'],'costs_complete':False})
        assert c.close(incomplete,actor='admin').code==422
        old=ok(t.create_title(title(data,key='OLD',issue_date='2026-10-01'),actor='admin'))
        assert c.close(closing(),actor='admin').code==422
        assert c.conference('A','2026-10')['pending_count']==1
        ok(a.recognize(request(data,cat,old,idempotency_key='OLD'),actor='admin'))
        ok(t.create_title(title(data,key='FUTURE',issue_date='2026-11-01',first_due='2026-11-30'),actor='admin'))
        assert c.conference('A','2026-10')['pending_count']==0
        ok(c.close(closing(),actor='admin'))
        assert a.statement(options(date_to='2026-10-31'))['status']=='CLOSED_MANAGERIAL'


def test_dashboard_matches_dre_previous_period_and_null_margins(app):
    with app.app_context():
        data=setup();source,cat,payload,entry=recognized(data)
        value=dashboard.dashboard(options(date_to='2026-10-31'))
        net=next(row for row in value['indicators'] if row['code']=='NET_RESULT')
        assert net['amount']=='-100' and net['margin_percent'] is None and net['change_percent'] is None
        recognized(data,group='REVENUE',kind='RECEIVABLE',total='200',key='REV')
        recognized(data,group='REVENUE',kind='RECEIVABLE',total='100',key='PREV',period='2026-09')
        value=dashboard.dashboard(options(date_to='2026-10-31'))
        revenue=next(row for row in value['indicators'] if row['code']=='NET_REVENUE')
        net=next(row for row in value['indicators'] if row['code']=='NET_RESULT')
        assert revenue['amount']=='200' and revenue['previous']=='100' and revenue['change_percent']=='100'
        assert net['amount']=='100' and net['margin_percent']=='50'
        assert value['previous_from']=='2026-09-01' and value['previous_to']=='2026-09-30'
        assert value['monthly'][0]['net_result']=='100'
        assert value['categories'][0]['amount']=='100'


def stock_data():
    from tests.test_organization_stock import _criar_material,move
    material=_criar_material()
    move(material,quantity='10',cost='5',key='IN')
    out=move(material,quantity='2',kind='saida',cost=None,key='SALE')
    return material,out['movimentacao']


def test_cost_contract_single_origin_no_stock_change_and_capitalization(app):
    from tests.test_organization_stock import move
    from addons.addon_estoque.root.model.organization_stock import OrganizationBalance
    with app.app_context():
        data=setup();material,movement=stock_data()
        move(material,quantity='1',kind='saida',cost=None,key='production:example')
        move(material,quantity='1',kind='saida',cost=None,key='packaging:example')
        costs=a.cost_review('A')
        assert len([row for row in costs['items'] if row['eligible']])==1
        assert len([row for row in costs['items'] if row['capitalized']])==2
        assert len(costs['pending'])==1
        cat=ok(a.classify(classification(data,group='COST'),actor='admin'))
        payload={'organization_code':'A','source_type':'STOCK','source_id':movement['id'],'component':'COST_OF_SALES','reference':'Custo saída SALE',
            'classification_id':cat['id'],'effect':'RECOGNIZE','amount':'10','currency_code':'BRL','policy_version_id':None,'reason':'Destinação conferida','idempotency_key':'STOCK1',
            'allocations':[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'10'}]}
        before=OrganizationBalance.query.filter_by(organization_code='A').one().to_dict()
        assert a.preview(payload,actor='admin').success
        assert a.recognize(payload,actor='admin').success
        assert a.recognize({**payload,'idempotency_key':'STOCK2'},actor='admin').code==422
        assert OrganizationBalance.query.filter_by(organization_code='A').one().to_dict()==before
        assert next(row for row in a.statement(options())['rows'] if row['code']=='COST')['total']=='-10'
        assert not a.cost_review('A')['pending']
        capitalized=next(row for row in costs['items'] if row['capitalized'])
        assert a.recognize({**payload,'source_id':capitalized['movement_id'],'amount':'5','idempotency_key':'CAP'},actor='admin').code==422
        ok(c.close(closing(),actor='admin'))


def test_dashboard_costs_closing_screens_and_api(client,app):
    _login_admin(app,client)
    with app.app_context():data=setup();recognized(data)
    for view in ('dashboard','dre','costs','closing'):
        response=client.get('/financeiro/',query_string=options(tab='results',view=view,date_to='2026-10-31'))
        assert response.status_code==200,response.data.decode()[:3000]
        assert b'id="finance-workspace"' in response.data
    assert client.get('/api/financeiro/results/dashboard',query_string=options(date_to='2026-10-31')).status_code==200
    result=client.post('/api/financeiro/results/close',json=closing())
    assert result.status_code==201,result.json
    assert client.post('/api/financeiro/results/closures/'+str(result.json['item']['id'])+'/reopen',json={'reason':'Revisão','idempotency_key':'OPEN'}).status_code==201


@pytest.mark.parametrize('operation',['close','reverse-race'])
def test_concurrent_closing_serializes_accrual_mutations(app,tmp_path,operation):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        data=setup();source,cat,payload,entry=recognized(data)
        original,engine=_file_database(app,tmp_path)
    def worker(i):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                result=a.reverse(entry['id'],{'reason':'Corrigir','idempotency_key':'RACE'},actor='admin') if operation=='reverse-race' and i else c.close(closing(),actor='admin')
                results.append(result)
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        assert sum(r.success for r in results)==(2 if operation=='close' else 1)
        with app.app_context():
            if operation=='close':assert c.Close.query.count()==c.ActiveClose.query.count()==1
            else:assert c.Close.query.count()+a.Reversal.query.count()==1
    finally:
        with app.app_context():db.session.remove();db.engines[None]=original;engine.dispose()


def test_closing_migration_roundtrip_schema_guard_and_populated_protection(app):
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration=importlib.import_module('migrations.versions.a93dbe671ca5_finance_result_closing')
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade();migration.upgrade();migration.downgrade();migration.upgrade()
        assert len(sa.inspect(connection).get_table_names())==3
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_financeiro_result_close (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError):migration.upgrade()
        assert len(sa.inspect(connection).get_table_names())==1
    with app.app_context():
        data=setup();recognized(data);ok(c.close(closing(),actor='admin'))
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                with pytest.raises(RuntimeError):migration.downgrade()


def test_optional_stock_and_permissions(app,client,monkeypatch):
    from model.core.user import User
    _login_admin(app,client)
    with app.app_context():
        setup()
        monkeypatch.delitem(app.module_manager._registered_modules,'estoque')
        assert not a.cost_review('A')['available']
        assert c.conference('A','2026-10')['pending_count']==0
        ok(c.close(closing(),actor='admin'))
    monkeypatch.setattr(User,'has_permission',lambda self,key:key!='financial_results.list')
    assert client.get('/api/financeiro/results/dashboard?organization_code=A&date_from=2026-10-01&date_to=2026-10-31').status_code==403
