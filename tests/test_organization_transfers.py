"""Pareamento, custo contábil, câmbio e rollback de transferências."""
from decimal import Decimal
import pytest
from tests.test_addon_estoque import app, client, _login_admin, _criar_material
from tests.test_organization_stock import finance, move, DATE
from tests.test_purchase_integrity import _file_database
from core.db import db
from services.core.organization_service import save_organization
from addons.addon_estoque.root.model.organization_stock import OrganizationBalance, OrganizationMovement
from addons.addon_estoque.root.model.movimentacao import Movimentacao
from addons.addon_estoque.root.services import estoque_service as stock
from addons.addon_financeiro.root.services.exchange_service import create_rate
from addons.addon_financeiro.root.services.policy_version_service import create_policy_version


def payload(material, **changes):
    return {'source_organization':'A','destination_organization':'B','material_id':material.id,
        'quantity':'1','operation_date':DATE,'source_policy_version_id':None,'destination_policy_version_id':None,
        'rate_id':None,'idempotency_key':'TRANSFER-1','notes':None} | changes


def setup(currency='BRL'):
    finance('A'); finance('B', currency)
    material = _criar_material()
    move(material, quantity='3', cost='1.115')
    return material


def test_transfer_preserves_total_quantity_value_legacy_and_frozen_link(app):
    with app.app_context():
        material = setup()
        stock.registrar_movimentacao(material.id,'entrada',99,custo_unitario=9)
        result = stock.transferir_entre_organizacoes(payload(material),actor='admin')
        assert not result['replayed']
        assert result['saida']['saldo']['quantidade_atual']=='2'
        assert result['saida']['movimentacao']['custo_total']=='-1.12'
        assert result['entrada']['saldo']['valor_total_estoque']=='1.12'
        assert sum(b.quantity for b in OrganizationBalance.query.all())==3
        assert sum(b.stock_value for b in OrganizationBalance.query.all())==Decimal('3.35')
        outgoing, incoming = result['saida']['movimentacao'], result['entrada']['movimentacao']
        assert outgoing['snapshot']['transfer_reference']==incoming['snapshot']['transfer_reference']==result['transfer_reference']
        assert incoming['snapshot']['outgoing_movement_id']==outgoing['id']
        assert stock.consultar_saldo(material.id)['quantidade_atual']==99
        assert Movimentacao.query.count()==1 and OrganizationMovement.query.count()==3


def test_same_currency_different_precision_carries_exact_cost_without_second_rounding(app):
    with app.app_context():
        finance('A'); finance('B')
        version = create_policy_version({'organization_code':'A','decimal_places':6,'rounding':'HALF_UP',
            'valid_from':DATE,'reason':'Precisão','expected_version':1},actor='admin')
        assert version.success, version.error
        material = _criar_material()
        move(material, quantity='1', cost='0.123456', policy_version_id=version.data['id'])
        result = stock.transferir_entre_organizacoes(payload(material,source_policy_version_id=version.data['id']),actor='admin')
        assert result['entrada']['movimentacao']['custo_total']=='0.123456'
        assert result['saida']['saldo']['valor_total_estoque']=='0'
        assert result['entrada']['movimentacao']['snapshot']['same_currency_cost_carried']


def test_foreign_transfer_requires_destination_rate_and_preserves_conversion(app):
    with app.app_context():
        material = setup('USD')
        data = payload(material)
        with pytest.raises(ValueError,match='taxa'):stock.transferir_entre_organizacoes(data,actor='admin')
        assert OrganizationMovement.query.count()==1
        assert stock.consultar_saldo(material.id,organization_code='A')['quantidade_atual']=='3'
        rate = create_rate({'organization_code':'B','source_currency':'BRL','target_currency':'USD','rate':'0.2',
            'valid_on':DATE,'source':'Contrato','rate_type':'CONTRACTUAL'},actor='admin')
        assert rate.success,rate.error
        result = stock.transferir_entre_organizacoes(data|{'rate_id':rate.data['id']},actor='admin')
        converted = result['entrada']['movimentacao']['snapshot']['conversion']
        assert converted['original_amount']=='1.12' and converted['converted_amount']=='0.22'
        assert converted['source_currency']=='BRL' and converted['target_currency']=='USD'
        assert result['entrada']['saldo']['currency_code']=='USD'


@pytest.mark.parametrize('field,value',[('quantity',True),('quantity',1.2),('quantity','0'),('quantity','-1'),
    ('quantity','NaN'),('quantity','9'),('destination_organization','A'),('destination_organization','MISSING'),
    ('material_id',True),('rate_id',True),('source_policy_version_id',True),('notes','x'*1001)])
def test_invalid_transfer_does_not_write_one_sided_movement(app,field,value):
    with app.app_context():
        material = setup()
        with pytest.raises(ValueError):stock.transferir_entre_organizacoes(payload(material,**{field:value}),actor='admin')
        assert OrganizationMovement.query.count()==1 and OrganizationBalance.query.count()==1
        assert OrganizationBalance.query.one().quantity==3


def test_replay_returns_original_both_balances_and_conflict_is_rejected(app):
    with app.app_context():
        material=setup();data=payload(material)
        first=stock.transferir_entre_organizacoes(data,actor='admin')
        move(material,code='B',cost='2',key='later')
        retry=stock.transferir_entre_organizacoes(data|{'quantity':'1.000','source_organization':' a '},actor='admin')
        assert retry['replayed'] and retry['saida']['saldo']==first['saida']['saldo']
        assert retry['entrada']['saldo']==first['entrada']['saldo']
        with pytest.raises(ValueError,match='dados diferentes'):
            stock.transferir_entre_organizacoes(data|{'quantity':'2'},actor='admin')
        assert OrganizationMovement.query.count()==4


def test_inactive_organization_and_destination_overflow_roll_back_outgoing(app):
    with app.app_context():
        material=setup()
        org=save_organization({'code':'C','name':'C','is_active':False}).data
        with pytest.raises(ValueError,match='ativas'):
            stock.transferir_entre_organizacoes(payload(material,destination_organization='C'),actor='admin')
        move(material,code='B',cost='999999999999999999',key='full')
        with pytest.raises(ValueError,match='magnitude'):stock.transferir_entre_organizacoes(payload(material),actor='admin')
        assert stock.consultar_saldo(material.id,organization_code='A')['quantidade_atual']=='3'
        assert OrganizationMovement.query.count()==2


def test_second_leg_and_final_commit_failure_roll_back_everything(app,monkeypatch):
    with app.app_context():
        material=setup();data=payload(material)
        original=stock.registrar_movimentacao
        calls=[]
        def fail_incoming(*args,**kwargs):
            calls.append(args[1])
            if args[1]=='entrada':raise ValueError('falha entrada')
            return original(*args,**kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(stock,'registrar_movimentacao',fail_incoming)
            with pytest.raises(ValueError,match='falha entrada'):stock.transferir_entre_organizacoes(data,actor='admin')
        assert calls==['saida','entrada']
        def fail_commit():raise RuntimeError('falha commit')
        with monkeypatch.context() as patch:
            patch.setattr(db.session,'commit',fail_commit)
            with pytest.raises(RuntimeError,match='falha commit'):stock.transferir_entre_organizacoes(data,actor='admin')
        assert OrganizationMovement.query.count()==1 and OrganizationBalance.query.count()==1
        assert OrganizationBalance.query.one().quantity==3
        assert 'organization_stock_transfer' not in db.session.info


def test_direct_half_transfer_and_reserved_keys_are_rejected(app):
    with app.app_context():
        material=setup()
        with pytest.raises(ValueError,match='Use transferir'):stock.registrar_movimentacao(material.id,'saida','1',
            organization_code='A',actor='admin',transfer_reference='arbitrary',commit=False)
        with pytest.raises(ValueError,match='reservado'):move(material,key='transfer:manual')
        assert OrganizationMovement.query.count()==1


def test_concurrent_same_transfer_has_only_two_legs_and_conserves_stock(app,tmp_path):
    import threading
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        material=setup();data=payload(material);original,engine=_file_database(app,tmp_path)
    def worker():
        try:
            with app.app_context():
                OrganizationBalance.query.all();barrier.wait(timeout=10)
                results.append(stock.transferir_entre_organizacoes(data,actor='admin'))
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker) for _ in range(2)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        assert sorted(result['replayed'] for result in results)==[False,True]
        with app.app_context():
            assert OrganizationMovement.query.count()==3
            assert sum(b.quantity for b in OrganizationBalance.query.all())==3
            assert sum(b.stock_value for b in OrganizationBalance.query.all())==Decimal('3.35')
    finally:
        with app.app_context():db.session.remove();db.engines[None]=original;engine.dispose()


def test_transfer_form_and_json_preserve_error_inputs_and_show_history(app,client):
    _login_admin(app,client)
    with app.app_context():material=setup();data=payload(material)
    path='/estoque/saldos/transferir'
    page=client.get(path+'?source_organization=A&destination_organization=B')
    assert page.status_code==200 and 'Confirmar saída e entrada' in page.get_data(as_text=True)
    form={key:'' if value is None else str(value) for key,value in data.items()}|{'quantity':'1,5'}
    response=client.post(path,data=form)
    assert response.status_code==422 and '1,5' in response.get_data(as_text=True)
    first=client.post(path,json=data)
    assert first.status_code==201,first.get_data(as_text=True)
    assert client.post(path,json=data).status_code==200
    assert 'Transferência A → B' in client.get('/estoque/saldos/por-organizacao?organization_code=B').get_data(as_text=True)


def test_transfer_helper_itself_rolls_back_a_failure_without_root_wrapper(app):
    from addons.addon_estoque.root.services.organization_transfer_service import transfer
    with app.app_context():
        material=setup('USD')
        with pytest.raises(ValueError,match='taxa'):transfer(payload(material),actor='admin')
        assert OrganizationMovement.query.count()==1 and OrganizationBalance.query.count()==1
        assert OrganizationBalance.query.one().quantity==3
        assert 'organization_stock_transfer' not in db.session.info


def test_rate_from_wrong_organization_or_date_cannot_confirm_either_leg(app):
    with app.app_context():
        material=setup('USD');finance('C','USD')
        for code,valid_on in [('C',DATE),('B','2026-10-08')]:
            rate=create_rate({'organization_code':code,'source_currency':'BRL','target_currency':'USD','rate':'0.2',
                'valid_on':valid_on,'source':'Teste','rate_type':'MANUAL'},actor='admin')
            assert rate.success,rate.error
            with pytest.raises(ValueError):stock.transferir_entre_organizacoes(payload(material,rate_id=rate.data['id']),actor='admin')
            assert OrganizationMovement.query.count()==1 and OrganizationBalance.query.count()==1


def test_concurrent_opposite_transfers_preserve_value_and_quantity_without_deadlock(app,tmp_path):
    import threading
    barrier=threading.Barrier(2);results=[];errors=[]
    with app.app_context():
        material=setup();move(material,code='B',quantity='3',cost='2',key='stock-B')
        data=payload(material);original,engine=_file_database(app,tmp_path)
    def worker(reverse):
        try:
            with app.app_context():
                OrganizationBalance.query.all();barrier.wait(timeout=10)
                request=data|({'source_organization':'B','destination_organization':'A'} if reverse else {})
                results.append(stock.transferir_entre_organizacoes(request,actor='admin'))
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=worker,args=(reverse,)) for reverse in (False,True)]
    try:
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=15)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors,errors
        assert len(results)==2 and not any(result['replayed'] for result in results)
        with app.app_context():
            assert OrganizationMovement.query.count()==6
            assert sum(b.quantity for b in OrganizationBalance.query.all())==6
            assert sum(b.stock_value for b in OrganizationBalance.query.all())==Decimal('9.35')
    finally:
        with app.app_context():db.session.remove();db.engines[None]=original;engine.dispose()


def test_transfer_endpoint_requires_login_and_permissions(app,client):
    from model.core.user import User
    with app.app_context():
        material=setup();data=payload(material)
        user=User(username='transfer_reader',email='reader@test.local',nome='Reader',nome_completo='Reader',
            celular='0',is_active=True,is_admin=False)
        user.set_password('secret');db.session.add(user);db.session.commit()
    path='/estoque/saldos/transferir'
    assert client.post(path,json=data).status_code in (401,302)
    assert client.post('/api/auth/login',json={'username':'transfer_reader','password':'secret'}).status_code==200
    assert client.post(path,json=data).status_code==403
    with app.app_context():assert OrganizationMovement.query.count()==1
