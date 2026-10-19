"""Competência: fontes únicas, conservação, classificações e resultado rastreável."""
from decimal import Decimal
import pytest
from tests.test_financeiro_treasury import app,client,setup,title,payment,ok,DATE,_login_admin
from core.db import db
from addons.addon_financeiro.root.services import treasury_service as t,accrual_service as s


def classification(data,group='OPERATING_EXPENSE',category=None,version=0,key='C1',**extra):
    return {'organization_code':data[0]['organization_code'],'category_id':(category or data[1])['id'],'group_code':group,
        'expected_version':version,'valid_from':'2026-10-01','reason':'Classificação documentada','idempotency_key':key,**extra}


def request(data,c,source,**extra):
    return {'organization_code':data[0]['organization_code'],'source_type':'TITLE','source_id':source['id'],'component':None,
        'reference':source['reference'],'classification_id':c['id'],'effect':'RECOGNIZE','amount':source['base_amount'],
        'currency_code':data[0]['currency_code'],'policy_version_id':None,'reason':'Competência revisada','idempotency_key':'E1',
        'allocations':[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':source['base_amount']}],**extra}


def options(**extra):return {'organization_code':'A','date_from':'2026-10-01','date_to':'2026-11-30',**extra}


def test_classification_immutable_versions_compatible_and_idempotent(app):
    with app.app_context():
        data=setup();c=ok(s.classify(classification(data),actor='admin'))
        assert s.classify(classification(data),actor='admin').code==200
        assert s.classify(classification(data,group='COST'),actor='admin').code==422
        assert s.classify(classification(data,group='REVENUE',key='BAD'),actor='admin').code==422
        newer=ok(s.classify(classification(data,group='COST',version=1,key='C2'),actor='admin'))
        assert newer['version']==2
        assert s.classify(classification(data,key='STALE'),actor='admin').code==422
        row=db.session.get(s.Classification,c['id']);row.group_code='COST'
        with pytest.raises(ValueError):db.session.commit()
        db.session.rollback()


def test_principal_once_split_exact_and_no_cash_mutation(app):
    with app.app_context():
        data=setup();c=ok(s.classify(classification(data),actor='admin'))
        source=ok(t.create_title(title(data,total='100.01',count=3),actor='admin'))
        payload=request(data,c,source,allocations=[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'33.33'},{'period':'2026-11','cost_center_id':data[3]['id'],'amount':'66.68'}])
        before=(t.Movement.query.count(),db.session.get(t.Account,data[0]['id']).balance)
        preview=ok(s.preview(payload,actor='admin'));assert s.Entry.query.count()==0
        first=ok(s.recognize(payload,actor='admin'));assert first['status']=='RECOGNIZED'
        assert s.recognize(payload,actor='admin').code==200
        assert s.recognize({**payload,'idempotency_key':'OTHER'},actor='admin').code==422
        assert before==(t.Movement.query.count(),db.session.get(t.Account,data[0]['id']).balance)
        result=s.statement(options())
        expense=next(row for row in result['rows'] if row['code']=='OPERATING_EXPENSE')
        assert expense['values']=={'2026-10':'-33.33','2026-11':'-66.68'} and expense['total']=='-100.01'
        ok(t.settle(source['installments'][0]['id'],payment(data,principal='33.33'),actor='admin'))
        assert s.statement(options())['rows']==result['rows']
        assert s.review('A')['count']==0


def test_validation_conservation_scale_centers_cancellation_and_reversal(app):
    with app.app_context():
        data=setup();other=setup(code='B');c=ok(s.classify(classification(data),actor='admin'));source=ok(t.create_title(title(data),actor='admin'))
        payload=request(data,c,source)
        for extra in ({'amount':'101'},{'amount':100.0},{'currency_code':'USD'},{'allocations':[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'99'}]},
            {'allocations':[{'period':'2026-10','cost_center_id':other[3]['id'],'amount':'100'}]},
            {'allocations':[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'99.999'},{'period':'2026-11','cost_center_id':data[3]['id'],'amount':'0.001'}]}):
            assert s.recognize({**payload,**extra},actor='admin').code==422
        row=ok(s.recognize(payload,actor='admin'))
        assert t.cancel_title(source['id'],{'reason':'Cancelar'},actor='admin').code==422
        reverse={'reason':'Revisar competência','idempotency_key':'R1'}
        ok(s.reverse(row['id'],reverse,actor='admin'))
        assert s.reverse(row['id'],reverse,actor='admin').code==200
        assert s.recognize(payload,actor='admin').data['status']=='REVERSED'
        second=ok(s.recognize({**payload,'idempotency_key':'E2'},actor='admin'))
        assert s.reverse(row['id'],reverse,actor='admin').code==200
        assert s.Active.query.one().entry_id==second['id']
        ok(s.reverse(second['id'],{**reverse,'idempotency_key':'R2'},actor='admin'))
        ok(t.cancel_title(source['id'],{'reason':'Cancelar'},actor='admin'))
        assert s.recognize({**payload,'idempotency_key':'E3'},actor='admin').code==422


def test_financial_component_separate_and_blocks_settlement_reversal(app):
    with app.app_context():
        data=setup();expense=ok(s.classify(classification(data),actor='admin'))
        financial=ok(s.classify(classification(data,group='FINANCIAL_EXPENSE',version=1,key='CF'),actor='admin'))
        source=ok(t.create_title(title(data),actor='admin'))
        ok(s.recognize(request(data,expense,source),actor='admin'))
        settled=ok(t.settle(source['installments'][0]['id'],payment(data,interest='2'),actor='admin'))
        pending=s.review('A')['items'];assert pending[0]['component']=='INTEREST'
        payload=request(data,financial,source,source_type='SETTLEMENT',source_id=settled['id'],component='INTEREST',amount='2',idempotency_key='FEE',
            allocations=[{'period':'2026-11','cost_center_id':data[3]['id'],'amount':'2'}])
        entry=ok(s.recognize(payload,actor='admin'))
        assert t.reverse(settled['id'],{'reason':'Reverter','operation_date':DATE,'idempotency_key':'REV'},actor='admin').code==422
        net=next(row for row in s.statement(options())['rows'] if row['code']=='NET_RESULT')
        assert net['total']=='-102'
        ok(s.reverse(entry['id'],{'reason':'Rever juros','idempotency_key':'RF'},actor='admin'))
        ok(t.reverse(settled['id'],{'reason':'Reverter','operation_date':DATE,'idempotency_key':'REV'},actor='admin'))
        assert s.recognize({**payload,'idempotency_key':'FEE2'},actor='admin').code==422


def test_manual_adjustments_reductions_and_current_version_not_retroactive(app):
    with app.app_context():
        data=setup();c=ok(s.classify(classification(data),actor='admin'));source=ok(t.create_title(title(data),actor='admin'))
        ok(s.recognize(request(data,c,source),actor='admin'))
        ok(s.classify(classification(data,group='COST',version=1,key='C2'),actor='admin'))
        payload=request(data,c,source,source_type='ADJUSTMENT',source_id=None,reference='DEPREC-OUT',amount='20',idempotency_key='ADJ',
            allocations=[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'20'}])
        ok(s.recognize(payload,actor='admin'))
        ok(s.recognize({**payload,'reference':'CORRECAO','effect':'REDUCE','amount':'5','idempotency_key':'RED',
            'allocations':[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'5'}]},actor='admin'))
        result=s.statement(options())
        assert next(row for row in result['rows'] if row['code']=='OPERATING_EXPENSE')['total']=='-115'
        assert next(row for row in result['rows'] if row['code']=='COST')['total']=='0'
        assert result['status']=='PARTIAL'


def test_review_scope_non_result_purchase_and_income_statement_subtotals(app):
    with app.app_context():
        data=setup();income=ok(s.classify(classification(data,group='REVENUE',category=data[2],key='REV-CAT'),actor='admin'))
        source=ok(t.create_title(title(data,kind='RECEIVABLE',total='500',key='REV'),actor='admin'))
        ok(s.recognize(request(data,income,source),actor='admin'))
        expense=ok(s.classify(classification(data),actor='admin'))
        payable=ok(t.create_title(title(data,key='OUT'),actor='admin'))
        ok(s.recognize(request(data,expense,payable,idempotency_key='OUT'),actor='admin'))
        result=s.statement(options(cost_center_id=data[3]['id']))
        assert next(row for row in result['rows'] if row['code']=='NET_RESULT')['total']=='400'
        assert result['pending_count']==0
        # Simula apenas a referência imutável de origem na criação de um título de compra.
        db.session.execute(t.Title.__table__.update().where(t.Title.id==payable['id']).values(source_reference='purchase:999'))
        db.session.commit();db.session.expire_all()
        entry=s.Entry.query.filter_by(source_key=f"title:{payable['id']}").one()
        ok(s.reverse(entry.id,{'reason':'Reclassificar compra','idempotency_key':'REV-PUR'},actor='admin'))
        assert s.recognize(request(data,expense,payable,idempotency_key='PUR-EXP'),actor='admin').code==422
        excluded=ok(s.classify(classification(data,group='NON_RESULT',version=1,key='NON'),actor='admin'))
        ok(s.recognize(request(data,excluded,payable,idempotency_key='PUR-NON'),actor='admin'))
        result=s.statement(options())
        assert next(row for row in result['rows'] if row['code']=='NET_RESULT')['total']=='500'
        assert result['details'][-1]['result_amount']=='0'


def test_readonly_preview_and_historical_inactive_reads(app):
    import sqlalchemy as sa
    from services.core.organization_service import save_organization
    with app.app_context():
        data=setup();c=ok(s.classify(classification(data),actor='admin'));source=ok(t.create_title(title(data),actor='admin'))
        statements=[]
        def track(connection,cursor,statement,parameters,context,executemany):statements.append(statement.strip().split()[0].upper())
        sa.event.listen(db.engine,'before_cursor_execute',track)
        try:
            ok(s.preview(request(data,c,source),actor='admin'));s.review('A');s.statement(options())
        finally:sa.event.remove(db.engine,'before_cursor_execute',track)
        assert set(statements)<={'SELECT'}
        assert not db.session.new and not db.session.dirty
        row=ok(s.recognize(request(data,c,source),actor='admin'))
        from model.core.organization import Organization
        ok(save_organization({'code':'A','name':'A','is_active':False},ident=Organization.query.filter_by(code='A').one().id))
        assert s.statement(options())['details'][0]['entry_id']==row['id']
        assert s.recognize(request(data,c,source),actor='admin').success
        assert s.reverse(row['id'],{'reason':'Inativa','idempotency_key':'BAD'},actor='admin').code==422


def test_migration_roundtrip_validation_populated_protection_and_full_chain(app):
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration=importlib.import_module('migrations.versions.f82cad560b94_finance_accrual')
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade();migration.upgrade();migration.downgrade();migration.upgrade()
        assert len(sa.inspect(connection).get_table_names())==5
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_financeiro_accrual_entry (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError):migration.upgrade()
        assert len(sa.inspect(connection).get_table_names())==1
    with app.app_context():
        data=setup();ok(s.classify(classification(data),actor='admin'))
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                with pytest.raises(RuntimeError):migration.downgrade()
        result=app.test_cli_runner().invoke(args=['db','upgrade'])
        assert result.exit_code==0,result.output


@pytest.mark.parametrize('operation',['classification','same-source','competing-source','reverse','cancel-race','settlement-race'])
def test_concurrent_accrual_operations(app,tmp_path,operation):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        data=setup();payload_class=classification(data)
        if operation!='classification':
            c=ok(s.classify({**payload_class,'group_code':'FINANCIAL_EXPENSE'} if operation=='settlement-race' else payload_class,actor='admin'));source=ok(t.create_title(title(data),actor='admin'));payload=request(data,c,source)
            if operation=='settlement-race':
                sid=ok(t.settle(source['installments'][0]['id'],payment(data,interest='2'),actor='admin'))['id']
                payload=request(data,c,source,source_type='SETTLEMENT',source_id=sid,component='INTEREST',amount='2',allocations=[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'2'}])
            if operation=='reverse':entry_id=ok(s.recognize(payload,actor='admin'))['id']
        original,engine=_file_database(app,tmp_path)
    def worker(i):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                if operation=='classification':result=s.classify(payload_class,actor='admin')
                elif operation=='same-source':result=s.recognize(payload,actor='admin')
                elif operation=='competing-source':result=s.recognize({**payload,'idempotency_key':'E'+str(i)},actor='admin')
                elif operation in ('cancel-race','settlement-race'):
                    if i==0:result=s.recognize(payload,actor='admin')
                    elif operation=='cancel-race':result=t.cancel_title(source['id'],{'reason':'Cancelar'},actor='admin')
                    else:result=t.reverse(sid,{'reason':'Reverter','operation_date':DATE,'idempotency_key':'RACE'},actor='admin')
                else:result=s.reverse(entry_id,{'reason':'Correção','idempotency_key':'R1'},actor='admin')
                results.append(result)
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        assert sum(r.success for r in results)==(1 if operation in ('competing-source','cancel-race','settlement-race') else 2),[r.error for r in results]
        with app.app_context():
            assert s.Classification.query.count()==1
            if operation not in ('classification','cancel-race','settlement-race'):assert s.Entry.query.count()==s.Allocation.query.count()==1
            if operation=='cancel-race':assert s.Entry.query.count()+t.Cancellation.query.count()==1
            if operation=='settlement-race':assert s.Entry.query.count()+t.Reversal.query.count()==1
            if operation=='reverse':assert s.Reversal.query.count()==1 and s.Active.query.count()==0
    finally:
        with app.app_context():db.session.remove();db.engines[None]=original;engine.dispose()


def test_workspace_forms_api_permissions_and_invalid_payloads(client,app,monkeypatch):
    from model.core.user import User
    _login_admin(app,client)
    with app.app_context():data=setup();source=ok(t.create_title(title(data),actor='admin'))
    response=client.post('/api/financeiro/results/classifications',json=classification(data))
    assert response.status_code==201,response.json
    c=response.json['item'];payload=request(data,c,source)
    assert client.post('/api/financeiro/results/recognitions/preview',json=payload).status_code==200
    assert client.post('/api/financeiro/results/recognitions',json=payload).status_code==201
    for view in ('dre','review','classifications','entries'):
        response=client.get('/financeiro/',query_string=options(tab='results',view=view))
        assert response.status_code==200,response.data.decode()[:2000]
        assert b'id="finance-workspace"' in response.data
    assert client.get('/api/financeiro/results/dre',query_string=options()).status_code==200
    assert client.get('/api/financeiro/results/dre',query_string=options(cost_center_id='bad')).status_code==422
    assert client.post('/api/financeiro/results/classifications',json={**classification(data),'group_code':{}}).status_code==422
    assert client.post('/api/financeiro/results/recognitions',json={**payload,'source_id':True}).status_code==422
    monkeypatch.setattr(User,'has_permission',lambda self,key:False)
    assert client.get('/api/financeiro/results/dre',query_string=options()).status_code==403
    assert client.get('/financeiro/',query_string=options(tab='results',view='dre')).status_code==403
    assert client.post('/api/financeiro/results/recognitions',json=payload).status_code==403


def test_html_preview_rateios_post_and_preserved_errors(client,app):
    _login_admin(app,client)
    with app.app_context():
        data=setup();c=ok(s.classify(classification(data),actor='admin'));source=ok(t.create_title(title(data,total='100.01'),actor='admin'))
    payload=request(data,c,source)
    payload={key:('' if value is None else value) for key,value in payload.items() if key!='allocations'}
    payload.update(allocation_period=['2026-10','2026-11'],allocation_amount=['33.33','66.68'],allocation_center=[str(data[3]['id'])]*2,action='preview')
    response=client.post('/financeiro/resultados/apropriar',query_string=options(view='entries'),data=payload)
    assert response.status_code==200,response.data.decode()[:3000]
    assert 'Prévia, sem gravação'.encode() in response.data
    with app.app_context():assert s.Entry.query.count()==0
    response=client.post('/financeiro/resultados/apropriar',query_string=options(view='entries'),data={**payload,'action':'confirm','allocation_amount':['33.33','66.69']})
    assert response.status_code==422
    assert b'value="66.69"' in response.data and b'value="2026-11"' in response.data
    response=client.post('/financeiro/resultados/apropriar',query_string=options(view='entries'),data={**payload,'action':'confirm'})
    assert response.status_code==302
    assert 'tab=results' in response.location and 'view=entries' in response.location
    assert client.get(response.location).status_code==200
    with app.app_context():assert s.Entry.query.count()==1 and s.Allocation.query.count()==2


def test_fx_carrying_value_frozen_and_financial_difference_separate(app):
    from tests.test_organization_stock import finance
    from addons.addon_financeiro.root.services.exchange_service import create_rate
    with app.app_context():
        data=setup();finance('B','USD')
        def rate(value,date):return ok(create_rate({'organization_code':'A','source_currency':'USD','target_currency':'BRL','rate':value,'valid_on':date,'source':'Contrato','rate_type':'CONTRACTUAL'},actor='admin'))['id']
        first=rate('5',DATE);later=rate('6','2026-10-17')
        source=ok(t.create_title(title(data,currency_code='USD',rate_id=first),actor='admin'))
        c=ok(s.classify(classification(data),actor='admin'))
        ok(s.recognize(request(data,c,source),actor='admin'))
        settled=ok(t.settle(source['installments'][0]['id'],payment(data,rate_id=later,operation_date='2026-10-17'),actor='admin'))
        financial=ok(s.classify(classification(data,group='FINANCIAL_EXPENSE',version=1,key='FIN'),actor='admin'))
        payload=request(data,financial,source,source_type='SETTLEMENT',source_id=settled['id'],component='FX',amount='100',idempotency_key='FX',
            allocations=[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':'100'}])
        ok(s.recognize(payload,actor='admin'))
        rate('7','2026-10-18')
        result=s.statement(options())
        assert next(row for row in result['rows'] if row['code']=='OPERATING_EXPENSE')['total']=='-500'
        assert next(row for row in result['rows'] if row['code']=='FINANCIAL_EXPENSE')['total']=='-100'
        assert next(row for row in result['rows'] if row['code']=='NET_RESULT')['total']=='-600'


@pytest.mark.parametrize('kind,component,group,expected',[
 ('PAYABLE','INTEREST','FINANCIAL_EXPENSE','-2'),('PAYABLE','FINE','FINANCIAL_EXPENSE','-3'),('PAYABLE','DISCOUNT','FINANCIAL_INCOME','4'),
 ('RECEIVABLE','INTEREST','FINANCIAL_INCOME','2'),('RECEIVABLE','FINE','FINANCIAL_INCOME','3'),('RECEIVABLE','DISCOUNT','FINANCIAL_EXPENSE','-4')])
def test_component_direction_by_payable_receivable(app,kind,component,group,expected):
    with app.app_context():
        data=setup();source=ok(t.create_title(title(data,kind=kind),actor='admin'))
        settled=ok(t.settle(source['installments'][0]['id'],payment(data,interest='2',fine='3',discount='4'),actor='admin'))
        c=ok(s.classify(classification(data,group=group,category=data[2] if group=='FINANCIAL_INCOME' else data[1]),actor='admin'))
        value=str(abs(Decimal(expected)))
        payload=request(data,c,source,source_type='SETTLEMENT',source_id=settled['id'],component=component,amount=value,
            allocations=[{'period':'2026-10','cost_center_id':data[3]['id'],'amount':value}])
        ok(s.recognize(payload,actor='admin'))
        assert s.statement(options())['details'][0]['result_amount']==expected
