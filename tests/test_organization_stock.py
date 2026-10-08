"""Segregação, decimais exatos, snapshots cambiais e transações de compras."""
import importlib
import json
from decimal import Decimal
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_addon_estoque import (app,client,_login_admin,_criar_material,_criar_unidade,
    _criar_pedido_compra,_criar_item_pedido_compra,_criar_processo_cotacao,_criar_cotacao,
    _criar_item_processo_cotacao,_criar_item_cotacao)
from tests.test_purchase_integrity import purchase, _file_database
from core.db import db
from services.core.organization_service import save_organization
from addons.addon_financeiro.root.services.monetary_service import create_currency,create_policy
from addons.addon_financeiro.root.model.monetary import Currency
from addons.addon_financeiro.root.services.exchange_service import create_rate
from addons.addon_financeiro.root.services.policy_version_service import create_policy_version
from addons.addon_estoque.root.model.organization_stock import OrganizationBalance,OrganizationMovement,OrderValuation
from addons.addon_estoque.root.model.saldo import Saldo
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
from addons.addon_estoque.root.services.purchase_context_service import bind_context,get_context
from addons.addon_estoque.root.services.order_valuation_service import prepare_valuation
from addons.addon_estoque.root.services.pedido_compra_service import PedidoCompraService
from addons.addon_estoque.root.services.material_unidade_service import MaterialUnidadeService
from addons.addon_estoque.root.services import estoque_service as stock

DATE='2026-10-09'
PLAN={'source_currency':'BRL','operation_date':DATE,'rate_id':None}


def finance(code='A',currency='BRL'):
    assert save_organization({'code':code,'name':code}).success
    if db.session.get(Currency,currency) is None:
        assert create_currency({'code':currency,'name':currency,'decimal_places':2}).success
    assert create_policy({'organization_code':code,'currency_code':currency,'rounding':'HALF_UP'}).success


def move(material,quantity='1',cost='1',code='A',kind='entrada',key='manual',**extra):
    return stock.registrar_movimentacao(material.id,kind,quantity,organization_code=code,custo_unitario=cost,
        actor='admin',operation_date=DATE,idempotency_key=key,
        **({'source_currency':'BRL'} if kind=='entrada' or (kind=='ajuste' and not quantity.startswith('-')) else {}),**extra)


def scoped_purchase():
    finance();pedido,item,unit=purchase()
    assert bind_context('order',pedido.id,{'organization_code':'A'},actor='admin').success
    assert PedidoCompraService().update(pedido.id,{'status':'confirmado'}).success
    return pedido,item,unit


def test_organizations_and_legacy_have_independent_quantities_values_and_currencies(app):
    with app.app_context():
        finance();finance('B','USD');material=_criar_material()
        stock.registrar_movimentacao(material.id,'entrada',100,custo_unitario=7)
        result=move(material,quantity='2',cost='1.005')
        assert result['saldo']['valor_total_estoque']=='2.01'
        other=stock.registrar_movimentacao(material.id,'entrada','3',organization_code='B',custo_unitario='9',source_currency='USD',
            actor='admin',operation_date=DATE,idempotency_key='manual')
        assert other['saldo']['currency_code']=='USD'
        assert stock.consultar_saldo(material.id,organization_code='A')['quantidade_atual']=='2'
        assert stock.consultar_saldo(material.id,organization_code='B')['quantidade_atual']=='3'
        assert stock.consultar_saldo(material.id)['quantidade_atual']==100
        assert Movimentacao.query.count()==1 and OrganizationMovement.query.count()==2


def test_sqlite_stores_full_decimal_quantity_as_text_without_float_roundtrip(app):
    with app.app_context():
        finance();material=_criar_material();quantity='12345678901234567.123456789012'
        move(material,quantity=quantity,cost='0')
        ident=material.id
        db.session.remove()
        assert stock.consultar_saldo(ident,organization_code='A')['quantidade_atual']==quantity
        stored=db.session.execute(sa.text('SELECT quantity,typeof(quantity) FROM tesseract_estoque_organization_balance')).one()
        assert stored==(quantity,'text')


def test_weighted_cost_outgoing_and_full_drain_keep_ledger_cache_reconcilable(app):
    with app.app_context():
        finance();material=_criar_material()
        move(material,quantity='3',cost='1',key='one');move(material,quantity='1',cost='2',key='two')
        assert stock.consultar_saldo(material.id,organization_code='A')['custo_medio']=='1.250000000000'
        move(material,quantity='1',cost=None,kind='saida',key='out')
        assert stock.consultar_saldo(material.id,organization_code='A')['valor_total_estoque']=='3.75'
        move(material,quantity='3',cost=None,kind='saida',key='drain')
        balance=OrganizationBalance.query.one()
        rows=OrganizationMovement.query.all()
        assert balance.quantity==sum(row.quantity_delta for row in rows)==0
        assert balance.stock_value==sum(row.value_delta for row in rows)==0
        assert rows[-1].value_delta==Decimal('-3.75')


def test_idempotency_returns_original_balance_and_conflict_has_no_write(app):
    with app.app_context():
        finance();material=_criar_material()
        original=move(material);move(material,key='later',cost='2')
        retry=move(material)
        assert retry['replayed'] and retry['saldo']==original['saldo']
        with pytest.raises(ValueError,match='idempotência'):move(material,cost='9')
        assert OrganizationMovement.query.count()==2
        assert OrganizationBalance.query.one().stock_value==Decimal(3)


@pytest.mark.parametrize('quantity,cost',[(True,'1'),(1.2,'1'),('NaN','1'),('0','1'),('-1','1'),('1',True),('1',1.2),('1','-1'),('1',None),('1','Infinity')])
def test_invalid_new_values_have_no_balance_or_ledger(app,quantity,cost):
    with app.app_context():
        finance();material=_criar_material()
        with pytest.raises(ValueError):move(material,quantity=quantity,cost=cost)
        assert OrganizationBalance.query.count()==OrganizationMovement.query.count()==0


def test_negative_adjustment_is_costed_from_local_balance_and_cannot_use_global_stock(app):
    with app.app_context():
        finance();material=_criar_material()
        stock.registrar_movimentacao(material.id,'entrada',100,custo_unitario=7)
        with pytest.raises(ValueError,match='insuficiente'):move(material,quantity='1',cost=None,kind='saida')
        move(material,quantity='2',cost='0.335',key='in')
        move(material,quantity='-1',cost=None,kind='ajuste',key='adjust')
        assert OrganizationBalance.query.one().stock_value==Decimal('0.33')
        assert Saldo.query.one().quantidade_atual==100


def test_receipt_requires_frozen_valuation_and_uses_original_foreign_rate_after_new_rates(app):
    with app.app_context():
        pedido,item,unit=scoped_purchase()
        assert create_currency({'code':'USD','name':'Dólar','decimal_places':2}).success
        rate=create_rate({'organization_code':'A','source_currency':'USD','target_currency':'BRL','rate':'5.125',
            'valid_on':DATE,'source':'Contrato','rate_type':'CONTRACTUAL'},actor='admin').data
        data=PLAN|{'source_currency':'USD','rate_id':rate['id']}
        plan=prepare_valuation(pedido.id,data,actor='admin')
        assert plan.success,plan.error
        assert prepare_valuation(pedido.id,data,actor='other').data==plan.data
        assert prepare_valuation(pedido.id,PLAN,actor='admin').code==409
        create_rate({'organization_code':'A','source_currency':'USD','target_currency':'BRL','rate':'9',
            'valid_on':DATE,'source':'Outro','rate_type':'MANUAL'},actor='admin')
        result=stock.receber_pedido_compra(pedido.id,actor='admin',dados_por_item={item.id:{'lote_fornecedor':'LOT-1'}})
        movement=result['movimentacoes'][0]
        assert movement['snapshot']['conversion']['converted_amount']=='1025.00'
        assert movement['snapshot']['conversion']['rate']['id']==rate['id']
        assert movement['snapshot']['lote_fornecedor']=='LOT-1'
        assert stock.consultar_saldo(item.material_id,organization_code='A')['quantidade_atual']=='50'
        assert stock.consultar_saldo(item.material_id,organization_code='A')['custo_medio']=='20.500000000000'
        assert Saldo.query.count()==Movimentacao.query.count()==0
        with pytest.raises(stock.PedidoCompraStatusInvalidoError):stock.receber_pedido_compra(pedido.id,actor='admin')
        assert OrganizationMovement.query.count()==1
        assert not PedidoCompraService().update(pedido.id,{'status':'cancelado'}).success


def test_missing_or_wrong_currency_rate_date_scope_and_version_have_no_plan(app):
    with app.app_context():
        pedido,_,_=scoped_purchase()
        finance('B')
        assert create_currency({'code':'USD','name':'USD','decimal_places':2}).success
        rate=create_rate({'organization_code':'B','source_currency':'USD','target_currency':'BRL','rate':'5',
            'valid_on':DATE,'source':'B','rate_type':'MANUAL'},actor='admin').data
        for data in [None,{},PLAN|{'extra':1},PLAN|{'source_currency':'MISSING'},PLAN|{'source_currency':'USD'},
                     PLAN|{'source_currency':'USD','rate_id':rate['id']},PLAN|{'rate_id':True},PLAN|{'policy_version_id':999}]:
            assert prepare_valuation(pedido.id,data,actor='admin').code==422
            assert OrderValuation.query.count()==0
        with pytest.raises(ValueError,match='avaliação monetária'):stock.receber_pedido_compra(pedido.id,actor='admin')
        assert OrganizationMovement.query.count()==0


def test_explicit_policy_revision_is_frozen_with_receipt(app):
    with app.app_context():
        pedido,item,_=scoped_purchase()
        # Estado de compra real persistido em Float, antes da avaliação; 1 × 1.005.
        item.quantidade=1;item.preco_unitario=1.005;item.quantidade_convertida_base=25;db.session.commit()
        version=create_policy_version({'organization_code':'A','expected_version':1,'decimal_places':2,'rounding':'HALF_EVEN',
            'valid_from':DATE,'reason':'Precisão aprovada'},actor='admin').data
        result=prepare_valuation(pedido.id,PLAN|{'policy_version_id':version['id']},actor='admin')
        assert result.success,result.error
        stock.receber_pedido_compra(pedido.id,actor='admin')
        assert OrganizationMovement.query.one().value_delta==Decimal('1.00')
        assert OrganizationMovement.query.one().to_dict()['snapshot']['policy']['version_id']==version['id']


def test_multiline_receipt_failure_rolls_back_ledger_balances_and_status(app,monkeypatch):
    with app.app_context():
        finance();first,first_item,unit=purchase()
        another=_criar_material(nome='Segundo',sku='SEGUNDO-ORG');otherunit=_criar_unidade(another,'PCT',25)
        _criar_item_pedido_compra(first,another,otherunit,quantidade=2,preco_unitario=50)
        assert bind_context('order',first.id,{'organization_code':'A'},actor='admin').success
        assert PedidoCompraService().update(first.id,{'status':'confirmado'}).success
        assert prepare_valuation(first.id,PLAN,actor='admin').success
        original=stock.registrar_movimentacao
        calls=[]
        def fail_second(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise ValueError('induced')
            return original(*args,**kwargs)
        with monkeypatch.context() as ctx:
            ctx.setattr(stock,'registrar_movimentacao',fail_second)
            with pytest.raises(ValueError,match='induced'):stock.receber_pedido_compra(first.id,actor='admin')
        assert OrganizationMovement.query.count()==OrganizationBalance.query.count()==0
        assert db.session.get(PedidoCompra,first.id).status=='confirmado'
        assert OrderValuation.query.count()==1 # preparação anterior é intencionalmente preservada
        assert len(stock.receber_pedido_compra(first.id,actor='admin')['movimentacoes'])==2


def test_immutable_history_and_material_unit_are_protected(app):
    with app.app_context():
        pedido,item,unit=scoped_purchase();assert prepare_valuation(pedido.id,PLAN,actor='admin').success
        stock.receber_pedido_compra(pedido.id,actor='admin')
        for row in (OrganizationMovement.query.one(),OrderValuation.query.one()):
            row.created_by='other'
            with pytest.raises(ValueError,match='imutável'):db.session.commit()
            db.session.rollback()
            db.session.delete(row)
            with pytest.raises(ValueError,match='imutável'):db.session.commit()
            db.session.rollback()
        assert not MaterialUnidadeService().update(unit.id,{'fator_para_base':30}).success


def generated_process():
    finance();process=_criar_processo_cotacao()
    assert bind_context('process',process.id,{'organization_code':'A'},actor='admin').success
    material=_criar_material();unit=_criar_unidade(material,'PCT',25)
    requested=_criar_item_processo_cotacao(process,material,unit)
    quote=_criar_cotacao(process);response=_criar_item_cotacao(quote,requested,preco_unitario=5)
    stock.selecionar_item_cotacao_vencedor(response.id)
    return process,response


def test_generation_propagates_context_without_receiving_stock(app):
    with app.app_context():
        process,response=generated_process()
        result=stock.gerar_pedidos_de_cotacao(process.id,actor='admin')
        ident=result['pedidos_gerados'][0]['id']
        assert get_context('order',ident).organization_code=='A'
        assert get_context('order',ident).created_by=='admin'
        assert response.pedido_compra_item_id is not None
        assert result['processo_cotacao']['status']=='finalizado'
        assert OrganizationMovement.query.count()==OrganizationBalance.query.count()==0


def test_generation_failure_leaves_no_partial_order_context_or_links(app,monkeypatch):
    from addons.addon_estoque.root.services import purchase_integrity_service as service
    with app.app_context():
        process,response=generated_process()
        original=service.operate
        def fail(kind,*args,**kwargs):
            if kind=='item':return service.Result(False,error='induced',code=422)
            return original(kind,*args,**kwargs)
        with monkeypatch.context() as ctx:
            ctx.setattr(service,'operate',fail)
            with pytest.raises(RuntimeError,match='induced'):stock.gerar_pedidos_de_cotacao(process.id,actor='admin')
        assert PedidoCompra.query.count()==ItemPedidoCompra.query.count()==0
        assert response.pedido_compra_item_id is None and process.status=='aberto'
        assert get_context('process',process.id) is not None
        assert len(stock.gerar_pedidos_de_cotacao(process.id,actor='admin')['pedidos_gerados'])==1


def test_json_html_preview_confirmation_and_existing_receipt_route(app,client):
    _login_admin(app,client)
    with app.app_context():
        pedido,item,_=scoped_purchase();ident=pedido.id;mid=item.material_id
    path=f'/estoque/pedido-compras/{ident}/avaliacao-monetaria'
    assert client.get(path).status_code==200
    preview=client.post(path,json=PLAN|{'action':'preview'})
    assert preview.status_code==200 and preview.json['data']['items'][0]['conversion']['converted_amount']=='200.00'
    assert client.post(path,json=PLAN|{'action':'confirm'}).status_code==201
    assert client.get(path).status_code==200
    assert client.post(f'/estoque/pedido-compras/{ident}/entrada-mercadoria',json={'itens':[]}).status_code==200
    page=client.get('/estoque/saldos/por-organizacao?organization_code=A')
    assert page.status_code==200 and '200.00' in page.get_data(as_text=True)
    result=client.get('/estoque/saldos/por-organizacao?organization_code=A',json={})
    assert result.json['balances'][0]['material_id']==mid
    with app.app_context():assert Saldo.query.count()==Movimentacao.query.count()==0


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_movements_do_not_lose_balances_or_duplicate_keys(app,tmp_path,same_key):
    import threading
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        finance();material=_criar_material();mid=material.id
        original,engine=_file_database(app,tmp_path)
    def worker(index):
        try:
            with app.app_context():
                material=db.session.get(Material,mid)
                barrier.wait(timeout=10)
                results.append(move(material,key='same' if same_key else f'key-{index}'))
        except Exception as exc:errors.append(exc)
    # A classe é explícita; nenhuma criação do helper ocorre nos trabalhadores.
    from addons.addon_estoque.root.model.material import Material
    threads=[threading.Thread(target=worker,args=(index,)) for index in range(2)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        with app.app_context():
            assert OrganizationMovement.query.count()==(1 if same_key else 2)
            assert OrganizationBalance.query.one().quantity==Decimal(1 if same_key else 2)
    finally:
        for thread in threads:thread.join(timeout=15)
        with app.app_context():db.session.remove();db.engines[None]=original
        engine.dispose()


migration=importlib.import_module('migrations.versions.a37c4d98f562_organization_stock')


def test_migration_exact_schema_repeat_and_guarded_downgrade(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        for table in ('material','material_unidade','item_pedido_compra','pedido_compra'):
            conn.exec_driver_sql(f'CREATE TABLE tesseract_estoque_{table}(id INTEGER PRIMARY KEY)')
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        migration.upgrade();migration.upgrade()
        names=[table.name for table in migration.definitions()]
        assert set(names)<=set(sa.inspect(conn).get_table_names())
        migration.downgrade();migration.upgrade()
        conn.exec_driver_sql("INSERT INTO tesseract_estoque_organization_balance VALUES(1,'A',1,'BRL','0','0','2026-10-09')")
        with pytest.raises(RuntimeError,match='preservados'):migration.downgrade()
        assert set(names)<=set(sa.inspect(conn).get_table_names())


def test_migration_incompatible_table_is_rejected_before_any_ddl(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE tesseract_estoque_organization_movement(id INTEGER PRIMARY KEY)')
        monkeypatch.setattr(migration,'op',Operations(MigrationContext.configure(conn)))
        with pytest.raises(RuntimeError,match='incompatível'):migration.upgrade()
        assert not sa.inspect(conn).has_table('tesseract_estoque_organization_balance')


def test_receipt_detects_changed_item_after_monetary_freeze(app):
    with app.app_context():
        pedido,item,_=scoped_purchase();assert prepare_valuation(pedido.id,PLAN,actor='admin').success
        item.preco_unitario=999;db.session.commit() # corrupção/edição fora dos contratos públicos
        with pytest.raises(ValueError,match='snapshot'):stock.receber_pedido_compra(pedido.id,actor='admin')
        assert OrganizationMovement.query.count()==OrganizationBalance.query.count()==0
        assert pedido.status=='confirmado'


def test_receipt_commit_failure_keeps_plan_but_rolls_back_physical_transaction(app,monkeypatch):
    with app.app_context():
        pedido,_,_=scoped_purchase();assert prepare_valuation(pedido.id,PLAN,actor='admin').success
        def fail():raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            with pytest.raises(stock.EstoqueConcorrenciaError):stock.receber_pedido_compra(pedido.id,actor='admin')
        assert OrganizationMovement.query.count()==OrganizationBalance.query.count()==0
        assert pedido.status=='confirmado' and OrderValuation.query.count()==1


@pytest.mark.parametrize('same_order',[True,False])
def test_concurrent_scoped_receipts_are_atomic_and_material_cache_is_shared_safely(app,tmp_path,same_order):
    import threading
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        order,item,unit=scoped_purchase();assert prepare_valuation(order.id,PLAN,actor='admin').success
        ids=[order.id,order.id]
        if not same_order:
            other=_criar_pedido_compra()
            _criar_item_pedido_compra(other,item.material,unit,quantidade=1,preco_unitario=200)
            assert bind_context('order',other.id,{'organization_code':'A'},actor='admin').success
            assert PedidoCompraService().update(other.id,{'status':'confirmado'}).success
            assert prepare_valuation(other.id,PLAN,actor='admin').success
            ids[1]=other.id
        original,engine=_file_database(app,tmp_path)
    def worker(ident):
        try:
            with app.app_context():
                db.session.get(PedidoCompra,ident)
                barrier.wait(timeout=10)
                results.append(stock.receber_pedido_compra(ident,actor='admin'))
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker,args=(ident,)) for ident in ids]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        if same_order:
            assert len(results)==len(errors)==1
            assert isinstance(errors[0],stock.PedidoCompraStatusInvalidoError)
        else:
            assert not errors,errors
            assert len(results)==2
        with app.app_context():
            assert OrganizationMovement.query.count()==(1 if same_order else 2)
            balance=OrganizationBalance.query.one()
            assert balance.quantity==Decimal(50 if same_order else 75)
            assert balance.stock_value==Decimal(200 if same_order else 400)
            assert Saldo.query.count()==Movimentacao.query.count()==0
    finally:
        for thread in threads:thread.join(timeout=15)
        with app.app_context():db.session.remove();db.engines[None]=original
        engine.dispose()


def test_api_rejects_invalid_values_and_authenticated_user_without_write_permission(app,client):
    from model.core.user import User
    _login_admin(app,client)
    with app.app_context():
        finance();material=_criar_material();mid=material.id
    path='/estoque/saldos/por-organizacao/movimentar'
    data={'organization_code':'A','material_id':mid,'tipo_movimentacao':'entrada','quantidade':'1','custo_unitario':'1',
          'source_currency':'BRL','operation_date':DATE,'rate_id':None,'idempotency_key':'api'}
    first=client.post(path,json=data)
    assert first.status_code==201
    assert client.post(path,json=data).status_code==200
    for bad in [data|{'quantidade':1.1},data|{'organization_code':'MISSING'},data|{'material_id':True},
                data|{'material_id':2**100},data|{'snapshot':{}},data|{'rate_id':True},data|{'idempotency_key':'receipt:bad'}]:
        assert client.post(path,json=bad).status_code==422
    client.post('/api/auth/logout')
    with app.app_context():
        user=User(username='stock_no_permission',email='noperm@test.local',nome='Reader',nome_completo='Reader',celular='0',is_active=True,is_admin=False)
        user.set_password('secret');db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json={'username':'stock_no_permission','password':'secret'})
    assert client.post(path,json=data).status_code==403
    assert client.get('/estoque/saldos/por-organizacao?organization_code=A').status_code==403
    with app.app_context():assert OrganizationMovement.query.count()==1


def test_html_preview_preserves_selected_parameters_and_does_not_freeze_or_receive(app,client):
    _login_admin(app,client)
    with app.app_context():pedido,_,_=scoped_purchase();ident=pedido.id
    response=client.post(f'/estoque/pedido-compras/{ident}/avaliacao-monetaria',data=PLAN|{'rate_id':'','action':'preview'})
    assert response.status_code==200
    text=response.get_data(as_text=True)
    assert 'value="BRL" selected' in text and '200.00' in text
    with app.app_context():assert OrderValuation.query.count()==OrganizationMovement.query.count()==0


def test_disabled_financeiro_preserves_legacy_and_history_but_refuses_new_monetary_operations(app,client,monkeypatch):
    from addons.addon_estoque.root.services.financial_stock_contract import stock_valuation_options
    _login_admin(app,client)
    with app.app_context():
        finance();material=_criar_material();move(material)
        modules={key:value for key,value in app.module_manager.active_modules.items() if key!='financeiro'}
        with monkeypatch.context() as ctx:
            ctx.setattr(app.module_manager,'_registered_modules',modules)
            assert not stock_valuation_options('A')['available']
            stock.registrar_movimentacao(material.id,'entrada',1,custo_unitario=1)
            with pytest.raises(ValueError,match='Ative o addon Financeiro'):move(material,key='disabled')
            assert client.get('/estoque/saldos/por-organizacao?organization_code=A').status_code==200
            assert OrganizationMovement.query.count()==1 and Movimentacao.query.count()==1


def test_stock_route_import_does_not_import_financeiro_models():
    import subprocess,sys
    code="import sys; import addons.addon_estoque.root.controller.organization_stock_hooks; assert not any(name.startswith('addons.addon_financeiro.') for name in sys.modules)"
    result=subprocess.run([sys.executable,'-c',code],text=True,encoding='utf-8',capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_direct_valuation_line_cannot_commit_a_partial_order_receipt(app):
    with app.app_context():
        order,item,_=scoped_purchase()
        plan=prepare_valuation(order.id,PLAN,actor='admin')
        assert plan.success
        with pytest.raises(ValueError,match='receber_pedido_compra'):
            stock.registrar_movimentacao(item.material_id,'entrada','50',organization_code='A',
                valuation_id=plan.data['id'],pedido_compra_item_id=item.id,actor='admin')
        assert OrganizationMovement.query.count()==OrganizationBalance.query.count()==0
        assert stock.receber_pedido_compra(order.id,actor='admin')['pedido_compra']['status']=='recebido'
        assert db.session.info.get('organization_receipt_order') is None


def test_cancel_after_valuation_preserves_frozen_item_references(app):
    from addons.addon_estoque.root.services.item_pedido_compra_service import ItemPedidoCompraService
    with app.app_context():
        order,item,_=scoped_purchase()
        assert prepare_valuation(order.id,PLAN,actor='admin').success
        assert PedidoCompraService().update(order.id,{'status':'cancelado'}).success
        assert not ItemPedidoCompraService().trash(item.id).success
        assert not db.session.get(ItemPedidoCompra,item.id).is_deleted
        assert OrderValuation.query.count()==1 and OrganizationMovement.query.count()==0


def test_failed_manual_html_entry_preserves_values_without_stock_write(app,client):
    _login_admin(app,client)
    with app.app_context():finance();material=_criar_material();ident=material.id
    data={'organization_code':'A','material_id':str(ident),'tipo_movimentacao':'entrada','quantidade':'2.5',
          'custo_unitario':'preço inválido','source_currency':'BRL','operation_date':DATE,'rate_id':'',
          'policy_version_id':'','idempotency_key':'referencia-preservada','observacoes':'Descrição digitada'}
    response=client.post('/estoque/saldos/por-organizacao/movimentar',data=data)
    assert response.status_code==422
    html=response.get_data(as_text=True)
    assert 'value="2.5"' in html and 'referencia-preservada' in html and 'Descrição digitada' in html
    assert 'preço inválido' in html and 'value="BRL" selected' in html
    with app.app_context():assert OrganizationBalance.query.count()==OrganizationMovement.query.count()==0
