"""Entrega 3: atomicidade, histórico, segregação e contratos de leitura."""
from decimal import Decimal
import importlib
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from tests.test_financeiro_treasury import app, client, setup, title, payment, ok, DATE, _login_admin
from core.db import db
from addons.addon_financeiro.root.services import treasury_service as t, cash_operations_service as s, cash_flow_service as f
from addons.addon_financeiro.root.model.cash_operations import (FinancialTransfer as Transfer, FinancialTransferReversal as Reversal,
    BankStatement as Statement,BankStatementLine as Line,BankReconciliation as Link,BankReconciliationUndo as Undo,ActiveBankReconciliation as Active)


def account(code='A',opening='0',name='Destino'):
    return ok(t.create_catalog('accounts',{'organization_code':code,'name':name,'kind':'BANK','opening_balance':opening,
        'opening_date':DATE,'policy_version_id':None},actor='admin'))


def transfer(data,dest,**extra):
    return {'organization_code':'A','source_account_id':data[0]['id'],'destination_account_id':dest['id'],'amount':'100.01',
        'operation_date':DATE,'policy_version_id':None,'idempotency_key':'T1','notes':None,**extra}


def statement(account_id,**extra):
    return {'account_id':account_id,'currency_code':'BRL','reference':'Extrato outubro','idempotency_key':'B1',
        'lines':[{'external_id':'E1','operation_date':DATE,'amount':'-100','description':'Pagamento'}],**extra}


def options(**extra): return {'organization_code':'A','date_from':DATE,'date_to':'2026-10-31',**extra}


def test_transfer_atomic_exact_replay_and_reversal(app):
    with app.app_context():
        data=setup(); dest=account(); request=transfer(data,dest)
        row=ok(s.transfer(request,actor='admin'))
        assert db.session.get(t.Account,data[0]['id']).balance==Decimal('899.99')
        assert db.session.get(t.Account,dest['id']).balance==Decimal('100.01')
        assert t.Movement.query.count()==4
        assert s.transfer(request,actor='admin').code==200
        assert s.transfer({**request,'amount':'100.02'},actor='admin').code==422
        reverse={'operation_date':DATE,'reason':'Correção','idempotency_key':'R1'}
        rev=ok(s.reverse_transfer(row['id'],reverse,actor='admin'))
        assert s.reverse_transfer(row['id'],reverse,actor='admin').code==200
        assert s.reverse_transfer(row['id'],{**reverse,'idempotency_key':'R2'},actor='admin').code==422
        assert db.session.get(t.Account,data[0]['id']).balance==1000
        assert db.session.get(t.Account,dest['id']).balance==0
        assert Transfer.query.count()==Reversal.query.count()==1
        assert s.transfer(request,actor='admin').data['status']=='REVERSED'
        assert t.Movement.query.count()==6
        assert s.transfer(transfer(data,dest,amount=0.1,idempotency_key='FLOAT'),actor='admin').code==422
        assert s.transfer(transfer(data,dest,amount='0.001',idempotency_key='SCALE'),actor='admin').code==422


def test_transfer_failure_second_leg_rolls_back_everything(app):
    with app.app_context():
        data=setup(); dest=account(opening='999999999999999999.99')
        assert s.transfer(transfer(data,dest),actor='admin').code==422
        assert Transfer.query.count()==0 and t.Movement.query.count()==2
        assert db.session.get(t.Account,data[0]['id']).balance==1000
        assert db.session.get(t.Account,dest['id']).balance==Decimal('999999999999999999.99')


def test_transfer_rejects_cross_organization_and_insufficient_reversal(app):
    with app.app_context():
        data=setup(); other=setup(code='B')[0]
        assert s.transfer(transfer(data,other),actor='admin').code==422
        dest=account(); item=ok(s.transfer(transfer(data,dest),actor='admin'))
        payable=ok(t.create_title(title(data),actor='admin'))
        ok(t.settle(payable['installments'][0]['id'],payment(data,account_id=dest['id']),actor='admin'))
        count=t.Movement.query.count()
        assert s.reverse_transfer(item['id'],{'operation_date':DATE,'reason':'Teste','idempotency_key':'R1'},actor='admin').code==422
        assert Reversal.query.count()==0 and t.Movement.query.count()==count
        assert db.session.get(t.Account,data[0]['id']).balance==Decimal('899.99')


def test_statement_preview_import_duplicates_and_csv(app):
    with app.app_context():
        data=setup(); request=statement(data[0]['id'])
        assert s.preview_statement(request).success
        assert Statement.query.count()==0 and not db.session.new and not db.session.dirty
        ok(s.import_statement(request,actor='admin'))
        assert s.import_statement(request,actor='admin').code==200
        assert s.import_statement({**request,'reference':'Outro'},actor='admin').code==422
        assert s.import_statement({**request,'idempotency_key':'B2'},actor='admin').code==409
        assert Line.query.count()==1 and Statement.query.count()==1
        assert db.session.get(t.Account,data[0]['id']).balance==1000 and t.Movement.query.count()==1
        assert s.import_statement({**request,'idempotency_key':'B3','currency_code':'USD'},actor='admin').code==422
        rows=s.csv_lines(b'external_id,operation_date,amount,description\nE2,2026-10-16,0.01,"a,b"\n')
        assert rows[0]['description']=='a,b'
        with pytest.raises(ValueError): s.csv_lines(b'external_id,date,amount,description\n')
        with pytest.raises(ValueError): s.csv_lines(b'x'*(2*1024*1024+1))


def test_reconciliation_same_amount_sign_account_dates_undo_and_relink(app):
    with app.app_context():
        data=setup(); payable=ok(t.create_title(title(data),actor='admin'))
        settlement=ok(t.settle(payable['installments'][0]['id'],payment(data),actor='admin'))
        movement=t.Movement.query.filter_by(reference=f"settlement:{settlement['id']}").one()
        ok(s.import_statement(statement(data[0]['id']),actor='admin')); line=Line.query.one()
        request={'movement_id':movement.id,'idempotency_key':'L1','date_difference_reason':None}
        row=ok(s.reconcile(line.id,request,actor='admin'))
        assert s.reconcile(line.id,request,actor='admin').code==200
        assert s.reconcile(line.id,{**request,'idempotency_key':'L2'},actor='admin').code==422
        assert f.reconciliation_data(options())['linked_count']==1
        undo={'reason':'Vínculo incorreto','idempotency_key':'U1'}
        ok(s.undo_reconciliation(row['id'],undo,actor='admin'))
        new=ok(s.reconcile(line.id,{**request,'idempotency_key':'L2'},actor='admin'))
        assert s.undo_reconciliation(row['id'],undo,actor='admin').code==200
        assert db.session.get(Active,line.id).reconciliation_id==new['id']
        assert s.reconcile(line.id,request,actor='admin').data['status']=='UNDONE'
        assert Link.query.count()==2 and Undo.query.count()==1
        assert db.session.get(t.Account,data[0]['id']).balance==900


def test_reconciliation_rejects_sign_cross_account_and_requires_date_reason(app):
    with app.app_context():
        data=setup(); dest=account(opening='100')
        ok(s.import_statement(statement(data[0]['id'],lines=[{'external_id':'E1','operation_date':'2026-10-17','amount':'1000','description':'Abertura'}]),actor='admin'))
        line=Line.query.one(); movement=t.Movement.query.filter_by(account_id=data[0]['id']).one()
        request={'movement_id':movement.id,'idempotency_key':'L1','date_difference_reason':None}
        assert s.reconcile(line.id,request,actor='admin').code==422
        wrong=t.Movement.query.filter_by(account_id=dest['id']).one()
        assert s.reconcile(line.id,{**request,'movement_id':wrong.id},actor='admin').code==422
        ok(s.reconcile(line.id,{**request,'date_difference_reason':'Compensação bancária no dia seguinte'},actor='admin'))
        assert Link.query.one().to_dict()['snapshot']['date_difference_reason']


def test_cash_flow_exact_internal_net_forecast_cancel_and_account_filter(app):
    with app.app_context():
        data=setup(); dest=account()
        ok(s.transfer(transfer(data,dest),actor='admin'))
        payable=ok(t.create_title(title(data,total='100.01'),actor='admin'))
        ok(t.settle(payable['installments'][0]['id'],payment(data,principal='40',interest='1'),actor='admin'))
        cancelled=ok(t.create_title(title(data,key='CANCEL'),actor='admin'))
        ok(t.cancel_title(cancelled['id'],{'reason':'Correção'},actor='admin'))
        value=f.cash_flow(options())
        assert value['closing_balance']=='959' and value['projected_balance']=='898.99'
        assert sum(Decimal(row['internal_net']) for row in value['items'])==0
        assert value['items'][-1]['pending_outflow']=='60.01'
        assert value['items'][-1]['planned_outflow']=='100.01'
        selected=f.cash_flow(options(account_id=dest['id']))
        assert selected['closing_balance']=='100.01' and not selected['forecast_available']
        assert all(row['pending_outflow']=='0' for row in selected['items'])
        with pytest.raises(ValueError): f.cash_flow(options(date_to='2028-01-01'))
        assert f.report_data('titles',options())['contract']=='financeiro.titles.v1'
        assert f.report_data('settlements',options())['items'][0]['status']=='POSTED'


def test_migration_upgrade_repeated_and_populated_downgrade_blocked(app):
    with app.app_context():
        migration=importlib.import_module('migrations.versions.e71b9d45fa83_finance_cash_operations')
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade(); migration.upgrade()
        data=setup();dest=account();ok(s.transfer(transfer(data,dest),actor='admin'))
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError): migration.downgrade()
        result=app.test_cli_runner().invoke(args=['db','upgrade'])
        assert result.exit_code==0,result.output


def test_screens_api_validation_and_automatic_menus(client,app):
    _login_admin(app,client)
    with app.app_context(): data=setup(); dest=account();request=transfer(data,dest)
    for path in ('/financeiro/fluxo-caixa/','/financeiro/lancamentos/','/financeiro/lancamentos/historico','/financeiro/transferencias/','/financeiro/conciliacao/'):
        response=client.get(path,query_string=options())
        assert response.status_code==200,response.data.decode()[:3000]
    response=client.post('/api/financeiro/operations/transfers',json=request)
    assert response.status_code==201,response.json
    assert client.get('/api/financeiro/operations/cash-flow',query_string=options()).status_code==200
    assert client.get('/api/financeiro/operations/cash-flow',query_string=options(account_id='x')).status_code==422
    assert client.post('/api/financeiro/operations/statements/preview',json={}).status_code==422
    assert client.get('/api/financeiro/operations/reconciliation',query_string=options()).status_code==200


@pytest.mark.parametrize('operation',['same-transfer','shared-balance','opposite-transfer','same-import','same-link','same-undo'])
def test_concurrent_operations(app,tmp_path,operation):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        data=setup(opening='100');dest=account(opening='100' if operation=='opposite-transfer' else '0')
        payload=transfer(data,dest,amount='80')
        if operation in ('same-link','same-undo'):
            ok(s.import_statement(statement(data[0]['id'],lines=[{'external_id':'E1','operation_date':DATE,'amount':'100','description':'Abertura'}]),actor='admin'))
            line_id=Line.query.one().id
            movement_id=t.Movement.query.filter_by(account_id=data[0]['id']).one().id
            link_payload={'movement_id':movement_id,'idempotency_key':'L1','date_difference_reason':None}
            if operation=='same-undo': link_id=ok(s.reconcile(line_id,link_payload,actor='admin'))['id']
        original,engine=_file_database(app,tmp_path)
    def worker(index):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                if operation=='same-transfer': result=s.transfer(payload,actor='admin')
                elif operation=='shared-balance': result=s.transfer({**payload,'idempotency_key':'T'+str(index)},actor='admin')
                elif operation=='opposite-transfer':
                    request=payload if index==0 else {**payload,'source_account_id':dest['id'],'destination_account_id':data[0]['id'],'idempotency_key':'T2'}
                    result=s.transfer(request,actor='admin')
                elif operation=='same-import':result=s.import_statement(statement(data[0]['id']),actor='admin')
                elif operation=='same-link':result=s.reconcile(line_id,link_payload,actor='admin')
                else:result=s.undo_reconciliation(link_id,{'idempotency_key':'U1','reason':'Correção'},actor='admin')
                results.append(result)
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        with app.app_context():
            assert sum(r.success for r in results)==(1 if operation=='shared-balance' else 2),[r.error for r in results]
            if operation in ('same-transfer','shared-balance'):
                assert Transfer.query.count()==1 and t.Movement.query.count()==4
                assert db.session.get(t.Account,data[0]['id']).balance==20
                assert db.session.get(t.Account,dest['id']).balance==80
            elif operation=='opposite-transfer':
                assert Transfer.query.count()==2
                assert db.session.get(t.Account,data[0]['id']).balance==100
                assert db.session.get(t.Account,dest['id']).balance==100
            elif operation=='same-import':assert Statement.query.count()==Line.query.count()==1
            elif operation=='same-link':assert Link.query.count()==Active.query.count()==1
            else:assert Undo.query.count()==1 and Active.query.count()==0
    finally:
        with app.app_context():db.session.remove();db.engines[None]=original;engine.dispose()


def test_history_immutable_reads_select_only_and_permission_boundaries(app,client,monkeypatch):
    from model.core.user import User
    _login_admin(app,client)
    with app.app_context():
        data=setup();dest=account();ok(s.transfer(transfer(data,dest),actor='admin'))
        ok(s.import_statement(statement(data[0]['id']),actor='admin'))
        row=Transfer.query.one();row.amount=Decimal('999')
        with pytest.raises(ValueError):db.session.commit()
        db.session.rollback()
        statements=[]
        def track(connection,cursor,statement,parameters,context,executemany):statements.append(statement.strip().split()[0].upper())
        sa.event.listen(db.engine,'before_cursor_execute',track)
        try:
            assert s.preview_statement(statement(data[0]['id'])).success
            f.cash_flow(options());f.reconciliation_data(options());f.report_data('titles',options())
        finally:sa.event.remove(db.engine,'before_cursor_execute',track)
        assert set(statements)<={'SELECT'},statements
    anonymous=app.test_client()
    assert anonymous.post('/api/financeiro/operations/transfers',json={}).status_code in (302,401)
    monkeypatch.setattr(User,'has_permission',lambda self,key:False)
    assert client.get('/financeiro/transferencias/').status_code==403
    assert client.get('/financeiro/conciliacao/').status_code==403
    assert client.get('/financeiro/fluxo-caixa/').status_code==403
    assert client.post('/api/financeiro/operations/transfers',json={}).status_code==403


def test_empty_migration_roundtrip_and_schema_prevalidation():
    module=importlib.import_module('migrations.versions.e71b9d45fa83_finance_cash_operations')
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.downgrade();module.upgrade()
        assert len(sa.inspect(connection).get_table_names())==7
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_financeiro_bank_statement (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError):module.upgrade()
        assert len(sa.inspect(connection).get_table_names())==1


def test_reconciliation_rejects_sign_and_one_movement_for_two_lines(app):
    with app.app_context():
        data=setup()
        ok(s.import_statement(statement(data[0]['id'],lines=[
            {'external_id':'NEG','operation_date':DATE,'amount':'-1000','description':'Sinal errado'},
            {'external_id':'POS','operation_date':DATE,'amount':'1000','description':'Crédito'},
            {'external_id':'POS2','operation_date':DATE,'amount':'1000','description':'Outro crédito'}]),actor='admin'))
        movement=t.Movement.query.one()
        lines=Line.query.order_by(Line.id).all()
        payload={'movement_id':movement.id,'idempotency_key':'L1','date_difference_reason':None}
        assert s.reconcile(lines[0].id,payload,actor='admin').code==422
        ok(s.reconcile(lines[1].id,payload,actor='admin'))
        assert s.reconcile(lines[2].id,{**payload,'idempotency_key':'L2'},actor='admin').code==422
        assert Active.query.count()==1
        assert f.reconciliation_data(options())['pending_count']==2
