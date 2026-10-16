"""Tesouraria: caixa exato, parcelas, baixas e estornos organizacionais."""
import json
from decimal import Decimal
import pytest
from tests.test_organization_stock import app, client, finance, _login_admin
from core.db import db
from addons.addon_financeiro.root.services import treasury_service as s
from addons.addon_financeiro.root.model.treasury import (FinancialAccount as Account, FinancialCategory as Category,
    FinancialCostCenter as Center, FinancialTitle as Title, FinancialInstallment as Installment,
    FinancialSettlement as Settlement, FinancialReversal as Reversal, FinancialCancellation as Cancellation, FinancialMovement as Movement)
from addons.addon_financeiro.root.services.exchange_service import create_rate

DATE = '2026-10-16'


def ok(result):
    assert result.success, result.error
    return result.data


def setup(*, opening='1000', code='A', currency='BRL', configure=True):
    if configure: finance(code, currency)
    account = ok(s.create_catalog('accounts', {'organization_code':code,'name':'Banco principal','kind':'BANK',
        'opening_balance':opening,'opening_date':DATE,'policy_version_id':None,'bank_name':'Banco','branch':'1','account_number':'123'}, actor='admin'))
    payable = ok(s.create_catalog('categories', {'organization_code':code,'name':'Compras','direction':'PAYABLE'},actor='admin'))
    receivable = ok(s.create_catalog('categories', {'organization_code':code,'name':'Vendas','direction':'RECEIVABLE'},actor='admin'))
    center = ok(s.create_catalog('cost-centers', {'organization_code':code,'name':'Operação'},actor='admin'))
    return account, payable, receivable, center


def title(data, *, kind='PAYABLE', total='100', count=1, key='TITLE-1', **extra):
    account, payable, receivable, center = data
    return {'organization_code':account['organization_code'],'kind':kind,'reference':'NF-001','counterparty':'Fornecedor' if kind=='PAYABLE' else 'Cliente',
        'currency_code':account['currency_code'],'amount':total,'issue_date':DATE,'first_due':'2026-10-31','installment_count':count,
        'category_id':(payable if kind=='PAYABLE' else receivable)['id'],'cost_center_id':center['id'],
        'rate_id':None,'policy_version_id':None,'idempotency_key':key, **extra}


def payment(data, principal='100', key='PAY-1', **extra):
    return {'account_id':data[0]['id'],'principal':principal,'interest':'0','fine':'0','discount':'0',
        'operation_date':DATE,'rate_id':None,'policy_version_id':None,'idempotency_key':key,'notes':None, **extra}


def test_accounts_catalogs_exact_balance_and_maintenance(app):
    with app.app_context():
        data=setup(opening='999999999999999999.99')
        aid=data[0]['id']; db.session.remove()
        row=db.session.get(Account,aid)
        assert row.balance == Decimal('999999999999999999.99')
        assert db.session.execute(db.text('SELECT typeof(balance) FROM tesseract_financeiro_treasury_account')).scalar()=='text'
        assert Movement.query.one().amount_delta == row.balance
        edited=ok(s.edit_catalog('accounts',aid,{'expected_version':1,'name':'Banco atualizado','is_active':False},actor='admin'))
        assert edited['version']==2 and not edited['is_active']
        assert s.edit_catalog('accounts',aid,{'expected_version':1,'name':'Outro','is_active':True},actor='admin').code==422
        assert s.edit_catalog('accounts',aid,{'expected_version':2,'name':'Outro','is_active':True,'organization_code':'B'},actor='admin').code==422
        assert row.balance == Decimal('999999999999999999.99')


def test_installments_conserve_original_and_base_with_calendar(app):
    with app.app_context():
        data=setup(); result=ok(s.create_title(title(data,total='100.01',count=3),actor='admin'))
        parts=result['installments']
        assert [row['due_date'] for row in parts]==['2026-10-31','2026-11-30','2026-12-31']
        assert [Decimal(row['amount']) for row in parts]==[Decimal('33.33'),Decimal('33.33'),Decimal('33.35')]
        assert sum(Decimal(row['base_amount']) for row in parts)==Decimal('100.01')
        assert s.create_title(title(data,total='100.01',count=3),actor='admin').code==200
        assert Title.query.count()==1 and Installment.query.count()==3 and Movement.query.count()==1
        assert s.create_title(title(data,total='100.02',count=3),actor='admin').code==422


def test_partial_payment_charges_discount_preview_and_exact_replay(app):
    with app.app_context():
        data=setup(); item=ok(s.create_title(title(data),actor='admin')); iid=item['installments'][0]['id']
        request=payment(data,principal='40',interest='2',fine='1',discount='5')
        preview=ok(s.preview_settlement(iid,request,actor='admin'))
        assert Decimal(preview['cash_base'])==38 and Settlement.query.count()==0 and Movement.query.count()==1
        assert not db.session.dirty and not db.session.new
        first=ok(s.settle(iid,request,actor='admin'))
        assert Decimal(first['cash_base'])==38
        assert s.title_detail(item['id'])['status']=='PARTIAL'
        assert Decimal(s.title_detail(item['id'])['remaining'])==60
        assert s.settle(iid,request,actor='admin').code==200
        assert Settlement.query.count()==1 and Movement.query.count()==2
        assert s.settle(iid,payment(data,principal='61',key='OVER'),actor='admin').code==422
        ok(s.settle(iid,payment(data,principal='60',key='REST'),actor='admin'))
        assert s.title_detail(item['id'])['status']=='PAID'
        assert db.session.get(Account,data[0]['id']).balance==902


def test_receipt_reversal_reopens_cancel_preserves_history(app):
    with app.app_context():
        data=setup(opening='0'); item=ok(s.create_title(title(data,kind='RECEIVABLE'),actor='admin')); iid=item['installments'][0]['id']
        settled=ok(s.settle(iid,payment(data),actor='admin'))
        assert db.session.get(Account,data[0]['id']).balance==100
        assert s.cancel_title(item['id'],{'reason':'Cancelar'},actor='admin').code==422
        reversal={'reason':'Baixa incorreta','operation_date':DATE,'idempotency_key':'REV-1'}
        assert s.reverse(settled['id'],reversal,actor='admin').code==201
        assert s.reverse(settled['id'],reversal,actor='admin').code==200
        assert db.session.get(Account,data[0]['id']).balance==0
        assert s.title_detail(item['id'])['status']=='OPEN'
        assert s.reverse(settled['id'],{**reversal,'idempotency_key':'REV-2'},actor='admin').code==422
        ok(s.cancel_title(item['id'],{'reason':'Cancelar'},actor='admin'))
        assert s.title_detail(item['id'])['status']=='CANCELLED'
        assert s.settle(iid,payment(data,key='AFTER-CANCEL'),actor='admin').code==422
        assert Movement.query.count()==3 and Settlement.query.count()==Reversal.query.count()==Cancellation.query.count()==1


def test_cross_organization_accounts_categories_and_insufficient_cash(app):
    with app.app_context():
        data=setup(opening='1'); other=setup(code='B')
        assert s.create_title({**title(data),'category_id':other[1]['id']},actor='admin').code==422
        assert s.create_title({**title(data),'cost_center_id':other[3]['id']},actor='admin').code==422
        assert s.create_title(title(data,kind='RECEIVABLE',category_id=data[1]['id']),actor='admin').code==422
        item=ok(s.create_title(title(data),actor='admin')); iid=item['installments'][0]['id']
        assert s.settle(iid,payment(other),actor='admin').code==422
        assert s.settle(iid,payment(data),actor='admin').code==422
        assert s.settle(iid,payment(data,discount='101'),actor='admin').code==422
        assert s.settle(iid,{**payment(data),'created_by':'forjado'},actor='admin').code==422
        assert s.settle(iid,payment(data,principal=True),actor='admin').code==422
        assert Settlement.query.count()==0 and Movement.query.count()==2
        assert db.session.get(Account,data[0]['id']).balance==1


def test_fx_payment_difference_is_frozen_and_reversal_uses_original_cash(app):
    with app.app_context():
        data=setup(); finance('B','USD')
        def rate(value,date):
            return ok(create_rate({'organization_code':'A','source_currency':'USD','target_currency':'BRL','rate':value,
                'valid_on':date,'source':'Contrato','rate_type':'CONTRACTUAL'},actor='admin'))['id']
        initial=rate('5',DATE); later=rate('6','2026-10-17')
        item=ok(s.create_title(title(data,total='100',currency_code='USD',rate_id=initial),actor='admin'))
        assert Decimal(item['base_amount'])==500
        result=ok(s.settle(item['installments'][0]['id'],payment(data,rate_id=later,operation_date='2026-10-17'),actor='admin'))
        assert Decimal(result['cash_base'])==600 and Decimal(result['snapshot']['exchange_difference'])==100
        assert Decimal(result['carrying_base'])==500
        assert db.session.get(Account,data[0]['id']).balance==400
        ok(s.reverse(result['id'],{'operation_date':'2026-10-18','reason':'Teste','idempotency_key':'REV'},actor='admin'))
        assert db.session.get(Account,data[0]['id']).balance==1000
        assert Decimal(s.title_detail(item['id'])['base_amount'])==500
        assert Settlement.query.one().cash_base==600


def test_invalid_decimal_inputs_and_installment_bounds_leave_no_title(app):
    with app.app_context():
        data=setup()
        for value in (True,1.5,'NaN','Infinity','1e2','1,20','-1','0','1.001'):
            assert not s.create_title(title(data,total=value),actor='admin').success, value
        for count in (True,0,121,1.5):
            assert not s.create_title(title(data,count=count),actor='admin').success
        assert not s.create_title(title(data,total='0.01',count=2),actor='admin').success
        assert Title.query.count()==Installment.query.count()==0


def test_all_payment_writes_roll_back_when_final_commit_fails(app,monkeypatch):
    with app.app_context():
        data=setup(); item=ok(s.create_title(title(data),actor='admin')); iid=item['installments'][0]['id']
        import sqlalchemy as sa
        with monkeypatch.context() as patch:
            patch.setattr(db.session,'commit',lambda: (_ for _ in ()).throw(sa.exc.OperationalError('commit',{},Exception('injected'))))
            assert s.settle(iid,payment(data),actor='admin').code==409
        assert Settlement.query.count()==0 and Movement.query.count()==1
        assert db.session.get(Account,data[0]['id']).balance==1000
        assert Decimal(s.title_detail(item['id'])['remaining'])==100


def test_orm_history_is_immutable_and_catalog_identity_cannot_change(app):
    with app.app_context():
        data=setup(); item=ok(s.create_title(title(data),actor='admin'))
        row=db.session.get(Title,item['id']); row.amount=Decimal(1)
        with pytest.raises(ValueError,match='imutável'): db.session.commit()
        db.session.rollback()
        account=db.session.get(Account,data[0]['id']); account.organization_code='B'
        with pytest.raises(ValueError,match='imutáveis'): db.session.commit()
        db.session.rollback()
        movement=Movement.query.first(); db.session.delete(movement)
        with pytest.raises(ValueError,match='imutável'): db.session.commit()
        db.session.rollback()


def test_title_preview_purchase_origin_and_rounding_preserve_stock(app):
    from tests.test_purchase_pricing import order, pricing
    from addons.addon_estoque.root.services.purchase_pricing_service import freeze
    from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
    from addons.addon_estoque.root.services.estoque_service import consultar_obrigacao_pedido
    from addons.addon_estoque.root.model.organization_stock import OrganizationMovement
    with app.app_context():
        order_row,line,_=order(); data=setup(configure=False)
        ok(freeze('order',order_row.id,pricing(line,quantity='2',price='0.123456789012',freight='1'),actor='admin'))
        assert PedidoCompraService().update(order_row.id,{'status':'confirmado'}).success
        source=consultar_obrigacao_pedido(order_row.id)
        request=title(data,total=source['amount'],purchase_order_id=order_row.id,counterparty=source['counterparty'])
        preview=ok(s.preview_title(request,actor='admin'))
        assert Decimal(preview['amount'])==Decimal('1.25')
        assert Title.query.count()==0 and OrganizationMovement.query.count()==0 and not db.session.dirty
        item=ok(s.create_title(request,actor='admin'))
        assert Decimal(item['amount'])==Decimal('1.25')
        assert item['snapshot']['purchase']['pricing']['freight']=='1'
        assert s.create_title({**request,'idempotency_key':'OTHER'},actor='admin').code==409
        assert OrganizationMovement.query.count()==0
        ok(s.settle(item['installments'][0]['id'],payment(data,principal='1.25'),actor='admin'))
        assert OrganizationMovement.query.count()==0
        assert consultar_obrigacao_pedido(order_row.id)['amount']==source['amount']
        assert s.create_title({**request,'idempotency_key':'BAD','amount':'2'},actor='admin').code==422


def test_html_api_permissions_forms_and_automatic_menus(app,client,monkeypatch):
    from model.core.transaction import Transaction
    from model.core.user import User
    from core.module_base import ModuleBase
    url='/api/financeiro/treasury'
    assert client.get(url+'/titles').status_code in (302,401)
    _login_admin(app,client)
    with app.app_context(): data=setup(); request=title(data); aid=data[0]['id']
    paths=['/financeiro/contas/','/financeiro/categorias/','/financeiro/centros-custo/','/financeiro/titulos/',
        '/financeiro/liquidacoes/','/financeiro/lancamentos/']
    for path in paths:
        response=client.get(path+'?organization_code=A')
        assert response.status_code==200,(path,response.get_data(as_text=True)[-500:])
    response=client.post(url+'/titles/preview',json=request)
    assert response.status_code==200 and response.json['success']
    response=client.post(url+'/titles',json=request)
    assert response.status_code==201,response.json
    item=response.json['item']; tid=item['id']; iid=item['installments'][0]['id']
    assert client.get(f'/financeiro/titulos/{tid}').status_code==200
    result=client.post(url+f'/installments/{iid}/preview',json=payment(data))
    assert result.status_code==200 and result.json['success']
    result=client.post(url+f'/installments/{iid}/settle',json=payment(data))
    assert result.status_code==201,result.json
    assert client.get(f'/financeiro/titulos/{tid}').status_code==200
    for path in ('titles','settlements','movements','catalogs/accounts'):
        response=client.get(url+'/'+path+'?organization_code=A')
        assert response.status_code==200 and response.json['success']
    posted={key:'' if value is None else str(value) for key,value in request.items()}
    posted.update(amount='1,23',reference='Referência digitada',idempotency_key='BAD-HTML')
    response=client.post('/financeiro/titulos/',data=posted)
    assert response.status_code==422 and 'Referência digitada' in response.get_data(as_text=True) and b'value="1,23"' in response.data
    response=client.post(f'/financeiro/contas/{aid}/editar?organization_code=A',data={
        'expected_version':'0','name':'Nome em conflito','is_active':'false','edit_id':str(aid)})
    assert response.status_code==422 and b'Nome em conflito' in response.data
    with app.app_context():
        module=app.module_manager.active_modules['financeiro']
        assert type(module).get_transactions is ModuleBase.get_transactions
        for path in paths:
            tx=Transaction.query.filter_by(route=path).one()
            assert tx.parent_id and tx.icon
    original=User.has_permission
    monkeypatch.setattr(User,'has_permission',lambda self,p: False if p=='admin' else original(self,p))
    assert client.post(url+'/titles',json=request).status_code==403
    assert client.post('/financeiro/titulos/',data=posted).status_code==403
    assert client.get('/financeiro/titulos/').status_code==200
    monkeypatch.setattr(User,'has_permission',lambda self,p: False if p=='financial_titles.list' else original(self,p))
    assert client.get('/financeiro/titulos/').status_code==403


def test_migration_repeat_schema_and_preserved_history(app):
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module=importlib.import_module('migrations.versions.d60a8c34e972_finance_treasury')
    with app.app_context():
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)): module.upgrade(); module.upgrade()
        data=setup()
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError,match='Downgrade bloqueado'): module.downgrade()
        assert db.session.get(Account,data[0]['id'])
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade(); module.downgrade(); module.upgrade()
        assert len(sa.inspect(connection).get_table_names())==9


def test_migration_incompatible_schema_fails_before_any_creation():
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module=importlib.import_module('migrations.versions.d60a8c34e972_finance_treasury')
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE tesseract_financeiro_treasury_movement (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError,match='incompatível'): module.upgrade()
        assert len(sa.inspect(connection).get_table_names())==1


@pytest.mark.parametrize('operation',['title','same-payment','overpayment','shared-cash','reversal'])
def test_concurrent_operations_preserve_debt_and_cash(app,tmp_path,operation):
    import threading
    from tests.test_purchase_integrity import _file_database
    barrier=threading.Barrier(2); results=[]; errors=[]
    with app.app_context():
        data=setup(opening='100' if operation=='shared-cash' else '1000')
        request=title(data); request_payment=payment(data)
        if operation!='title':
            item=ok(s.create_title(request,actor='admin')); iid=item['installments'][0]['id']
            if operation=='shared-cash':
                other=ok(s.create_title(title(data,key='OTHER'),actor='admin')); iid2=other['installments'][0]['id']
            if operation=='reversal':
                sid=ok(s.settle(iid,request_payment,actor='admin'))['id']
        original,engine=_file_database(app,tmp_path)
    def worker(index):
        try:
            with app.app_context():
                barrier.wait(timeout=10)
                if operation=='title': result=s.create_title(request,actor='admin')
                elif operation=='reversal': result=s.reverse(sid,{'reason':'Concorrência','operation_date':DATE,'idempotency_key':'REV'},actor='admin')
                elif operation=='same-payment': result=s.settle(iid,request_payment,actor='admin')
                elif operation=='overpayment': result=s.settle(iid,payment(data,principal='70',key='OVER-'+str(index)),actor='admin')
                else: result=s.settle(iid if index==0 else iid2,payment(data,principal='80',key='CASH-'+str(index)),actor='admin')
                results.append(result)
        except Exception as exc: errors.append(exc)
    threads=[threading.Thread(target=worker,args=(index,)) for index in range(2)]
    try:
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        with app.app_context():
            if operation=='title':
                assert all(result.success for result in results),[result.error for result in results]
                assert Title.query.count()==1
            elif operation in ('same-payment','reversal'):
                assert all(result.success for result in results),[result.error for result in results]
                assert Settlement.query.count()==1
                assert Reversal.query.count()==(1 if operation=='reversal' else 0)
                assert db.session.get(Account,data[0]['id']).balance==(1000 if operation=='reversal' else 900)
            else:
                assert sum(result.success for result in results)==1,[result.error for result in results]
                assert Settlement.query.count()==1
                assert db.session.get(Account,data[0]['id']).balance==(20 if operation=='shared-cash' else 930)
    finally:
        with app.app_context(): db.session.remove(); db.engines[None]=original; engine.dispose()


def test_previews_only_select_and_disabled_purchase_addon_refuses_source(app):
    import sqlalchemy as sa
    with app.app_context():
        data=setup(); item=ok(s.create_title(title(data),actor='admin')); iid=item['installments'][0]['id']
        statements=[]
        def track(connection,cursor,statement,parameters,context,executemany): statements.append(statement.strip().split()[0].upper())
        sa.event.listen(db.engine,'before_cursor_execute',track)
        try:
            ok(s.preview_title(title(data,key='PREVIEW'),actor='admin'))
            ok(s.preview_settlement(iid,payment(data),actor='admin'))
        finally: sa.event.remove(db.engine,'before_cursor_execute',track)
        assert set(statements)<= {'SELECT'},statements
        manager=app.module_manager; original=manager._registered_modules
        try:
            manager._registered_modules={key:value for key,value in original.items() if key!='estoque'}
            assert s.create_title(title(data,key='SOURCE',purchase_order_id=1),actor='admin').code==422
        finally: manager._registered_modules=original
        assert Title.query.count()==1


def test_reversal_insufficient_receipt_balance_keeps_all_original_events(app):
    with app.app_context():
        data=setup(opening='0')
        receipt=ok(s.create_title(title(data,kind='RECEIVABLE'),actor='admin'))
        income=ok(s.settle(receipt['installments'][0]['id'],payment(data),actor='admin'))
        payable=ok(s.create_title(title(data,key='OUT'),actor='admin'))
        ok(s.settle(payable['installments'][0]['id'],payment(data,key='OUT'),actor='admin'))
        assert s.reverse(income['id'],{'reason':'Saldo já utilizado','operation_date':DATE,'idempotency_key':'NOFUNDS'},actor='admin').code==422
        assert Reversal.query.count()==0 and Movement.query.count()==3
        assert s.title_detail(receipt['id'])['status']=='PAID'
