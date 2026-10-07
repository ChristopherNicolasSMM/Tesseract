import importlib
from decimal import Decimal
import json
import pytest
import requests
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_admin_users_pages import app, client, _login_admin
from core.db import db
from core.document_validation import DocumentValidator as V
from services.core.organization_service import save_organization, save_organization_contact, resolve_organization
from addons.addon_financeiro.root.model.monetary import Currency, MonetaryPolicy
from addons.addon_financeiro.root.services.monetary_service import create_currency, create_policy, resolve_policy, quantize_amount
from plugins.plugin_getcep.provider import ViaCEP, LookupError


@pytest.mark.parametrize('kind,value,expected', [
    ('cnpj','12.ABC.345/01DE-35','12ABC34501DE35'),
    ('cnpj','00.000.000/E08G-12','00000000E08G12'),
    ('cnpj','11.222.333/0001-81','11222333000181'),
    ('cpf','529.982.247-25','52998224725'), ('cep','01001-000','01001000'),
    ('phone','+55 (11) 99999-9999','+5511999999999'), ('email',' a@b.com ','a@b.com')])
def test_document_canonicalization(kind, value, expected):
    from addons.addon_financeiro.root.services.document_validator import DocumentValidator
    assert getattr(DocumentValidator, kind)(value) == expected


@pytest.mark.parametrize('kind,value', [('cnpj',True),('cnpj','00000000000000'),('cnpj','12.ABC.345/01DE-36'),
 ('cnpj','é2ABC34501DE35'),('cnpj','12ABC34501DE3A'),('cpf','52998224725a'),('cpf','11111111111'),
 ('cep','a01001000'),('cep','01001 000'),('cep',1001000),('phone','123'),('phone','phone11999999999'),
 ('email','x y@test.com')])
def test_document_rejects_bad_format_and_dv(kind,value):
    with pytest.raises(ValueError): getattr(V,kind)(value)


def test_profile_contacts_atomicity_and_cross_org_protection(app,monkeypatch):
    with app.app_context():
        a=save_organization({'code':'A','name':'Org','cnpj':'12.ABC.345/01DE-35','cep':'01001-000','estado':'sp'}).data
        assert a['cnpj']=='12ABC34501DE35' and a['estado']=='SP'
        assert save_organization({'code':'B','name':'Org2','cnpj':a['cnpj']}).code==409
        b=save_organization({'code':'B','name':'Org2'}).data
        assert all(b[key] is None for key in ('cnpj','legal_name','pais','cep'))
        assert save_organization({'name':'Changed','cep':'bad'},a['id']).code==422
        assert resolve_organization(a['id'])['name']=='Org'
        c=save_organization_contact(a['id'],{'name':'Pessoa','role':'Financeiro','cpf':'52998224725'}).data
        assert save_organization_contact(b['id'],{'name':'X'},c['id']).code==404
        assert save_organization_contact(a['id'],{'is_active':False},c['id']).success
        assert resolve_organization(a['id'])['contacts'][0]['is_active'] is False
        def fail(): raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            assert save_organization({'legal_name':'Alterada'},a['id']).code==409
            assert save_organization_contact(a['id'],{'name':'Changed'},c['id']).code==409
        assert resolve_organization(a['id'])['legal_name'] is None
        assert resolve_organization(a['id'])['contacts'][0]['name']=='Pessoa'


def setup_policy(code='A',rounding='HALF_UP'):
    assert save_organization({'code':code,'name':code}).success
    if db.session.get(Currency,'BRL') is None:
        assert create_currency({'code':'BRL','name':'Real','decimal_places':2}).success
    assert create_policy({'organization_code':code,'currency_code':'BRL','rounding':rounding}).success


@pytest.mark.parametrize('amount,up,even',[('1.005','1.01','1.00'),('-1.005','-1.01','-1.00'),('2.675','2.68','2.68'),('-0.001','0.00','0.00'),('999999999999999999.12','999999999999999999.12','999999999999999999.12')])
def test_decimal_rounding_and_frozen_policy(app,amount,up,even):
    with app.app_context():
        setup_policy('A');setup_policy('B','HALF_EVEN')
        assert quantize_amount(amount,'A')['amount']==up
        assert quantize_amount(Decimal(amount),'B')['amount']==even
        assert quantize_amount(amount,'A')['policy']['currency_code']=='BRL'
        assert create_policy({'organization_code':'A','currency_code':'BRL','rounding':'HALF_EVEN'}).code==409
        assert resolve_policy('A')['rounding']=='HALF_UP'


@pytest.mark.parametrize('amount',[True,1.005,'NaN','Infinity',Decimal('NaN'),Decimal('Infinity'),'1e2','1,00','1.0000000000001','1000000000000000000','999999999999999999.999'])
def test_unsafe_amounts_rejected(app,amount):
    with app.app_context():
        setup_policy()
        with pytest.raises(ValueError): quantize_amount(amount,'A')


@pytest.mark.parametrize('data',[{},[],{'code':'BRL','name':'Real','decimal_places':True},
 {'code':'brl','name':'Real','decimal_places':2},{'code':'BRL','name':'Real','decimal_places':7},
 {'code':'BRL','name':'Real','decimal_places':-1},{'code':'BRL','name':'','decimal_places':2}])
def test_invalid_currency_has_no_write(app,data):
    with app.app_context():
        assert create_currency(data).code==422
        assert Currency.query.count()==0


def test_no_implicit_policy_or_currency_and_commit_rollback(app,monkeypatch):
    with app.app_context():
        assert Currency.query.count()==0 and MonetaryPolicy.query.count()==0
        ident=save_organization({'code':'A','name':'Org'}).data['id']
        with pytest.raises(ValueError,match='sem política'): resolve_policy('A')
        assert create_policy({'organization_code':'A','currency_code':'BRL','rounding':'HALF_UP'}).code==422
        create_currency({'code':'BRL','name':'Real','decimal_places':2})
        assert create_policy({'organization_code':'A','currency_code':'BRL','rounding':None}).code==422
        def fail(): raise sa.exc.OperationalError('commit',{},Exception('induced'))
        with monkeypatch.context() as ctx:
            ctx.setattr(db.session,'commit',fail)
            assert create_policy({'organization_code':'A','currency_code':'BRL','rounding':'HALF_UP'}).code==409
        assert MonetaryPolicy.query.count()==0
        setup_policy('B')
        save_organization({'is_active':False},ident)
        assert create_policy({'organization_code':'A','currency_code':'BRL','rounding':'HALF_UP'}).code==422


PAYLOAD={'cep':'01001-000','logradouro':'Praça da Sé','bairro':'Sé','localidade':'São Paulo','uf':'SP'}
class Response:
    def __init__(self,payload=PAYLOAD,status=200,raw=None): self.status_code=status;self.raw=raw if raw is not None else json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,**kwargs): yield self.raw


def test_provider_fixed_url_cache_isolation_bounds_and_expiry():
    calls=[];now=[0]
    def transport(url,**kwargs): calls.append((url,kwargs));return Response()
    p=ViaCEP(transport=transport,clock=lambda:now[0])
    first=p.lookup('01001-000');first['cidade']='mutated'
    assert p.lookup('01001000')['cidade']=='São Paulo' and len(calls)==1
    assert calls[0]==('https://viacep.com.br/ws/01001000/json/',{'timeout':(2,3),'allow_redirects':False,'stream':True})
    now[0]=3601;p.lookup('01001000');assert len(calls)==2
    def dynamic(url,**kwargs): return Response(PAYLOAD|{'cep':url.split('/')[-3]})
    p=ViaCEP(transport=dynamic)
    for i in range(257):p.lookup(f'{i:08}')
    assert len(p.cache)==256 and '00000000' not in p.cache
    with pytest.raises(ValueError):p.lookup('https://localhost')


@pytest.mark.parametrize('response,status',[ (Response({'erro':True}),404),(Response(status=302),503),
 (Response(raw=b'x'),503),(Response(raw=b'x'*16385),503),(Response([]),503),
 (Response(PAYLOAD|{'cep':'02002000'}),503),(Response(PAYLOAD|{'uf':'ZZ'}),503),
 (Response(PAYLOAD|{'logradouro':None}),503)])
def test_provider_bad_response(response,status):
    p=ViaCEP(transport=lambda *args,**kwargs:response)
    with pytest.raises(LookupError) as exc:p.lookup('01001000')
    assert exc.value.status==status and not p.cache


def test_provider_timeout():
    def fail(*args,**kwargs):raise requests.Timeout()
    with pytest.raises(LookupError,match='manual'):ViaCEP(transport=fail).lookup('01001000')


def test_api_forms_plugin_loading_and_no_generic_mutation(app,client):
    assert client.get('/api/plugins/getcep/01001000').status_code==401
    assert client.get('/api/financeiro/currencies').status_code==401
    _login_admin(app,client)
    with app.app_context():
        assert 'getcep' in app.module_manager._registered_modules
        from model.core.transaction import Transaction
        tx=Transaction.query.filter_by(code='FIN_SETUP').one()
        assert tx.permission_required=='admin' and tx.route=='/financeiro/'
        assert not any('getcep' in table for table in db.metadata.tables)
    app.extensions['getcep_provider'].transport=lambda *a,**kw:Response()
    assert client.get('/api/plugins/getcep/01001000').get_json()['address']['estado']=='SP'
    assert client.get('/api/plugins/getcep/bad').status_code==422
    assert client.get('/api/plugins/getcep/assets/getcep.js').status_code==200
    ident=client.post('/api/admin/organizations/',json={'code':'A','name':'Org','cnpj':'12ABC34501DE35'}).get_json()['item']['id']
    assert client.post(f'/api/admin/organizations/{ident}/contacts',json={'name':'Pessoa','role':'Diretor'}).status_code==201
    assert client.post('/api/financeiro/currencies',json={'code':'BRL','name':'Real','decimal_places':2}).status_code==201
    assert client.post('/api/financeiro/policies',json={'organization_code':'A','currency_code':'BRL','rounding':'HALF_UP'}).status_code==201
    assert client.put('/api/financeiro/policies',json={}).status_code==405
    assert client.delete('/api/financeiro/currencies').status_code==405
    assert client.get('/financeiro/').status_code==200
    page=client.get('/admin/organizations/').data
    assert b'Raz' in page and b'name="cnpj"' in page and b'name="role"' in page and b'getcep.js' in page
    assert b'getcep.js' in client.get('/estoque/enderecos/').data


old=importlib.import_module('migrations.versions.a71c8d32f906_core_organizations')
new=importlib.import_module('migrations.versions.b82d9e43a017_financeiro_organizacoes')

def operations(conn):return Operations(MigrationContext.configure(conn))


def test_migration_preserves_existing_org_idempotence_and_downgrade(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        monkeypatch.setattr(old,'op',operations(conn));monkeypatch.setattr(new,'op',operations(conn))
        old.upgrade()
        conn.exec_driver_sql("INSERT INTO tesseract_organization VALUES(1,'A','Org',1,'2026-10-07','2026-10-07')")
        new.upgrade();new.upgrade();old.upgrade()
        assert conn.exec_driver_sql('SELECT id,code,cnpj FROM tesseract_organization').one()==(1,'A',None)
        new.downgrade();new.downgrade()
        assert len(sa.inspect(conn).get_columns('tesseract_organization'))==6
        assert conn.exec_driver_sql('SELECT code FROM tesseract_organization').scalar()=='A'


@pytest.mark.parametrize('target',['profile','contact','currency','policy'])
def test_migration_downgrade_protects_data(monkeypatch,target):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        monkeypatch.setattr(old,'op',operations(conn));monkeypatch.setattr(new,'op',operations(conn));old.upgrade();new.upgrade()
        conn.exec_driver_sql("INSERT INTO tesseract_organization(id,code,name,is_active,created_at,updated_at) VALUES(1,'A','Org',1,'2026-10-07','2026-10-07')")
        if target=='profile':conn.exec_driver_sql("UPDATE tesseract_organization SET legal_name='Legal'")
        if target=='contact':conn.exec_driver_sql("INSERT INTO tesseract_organization_contact(organization_id,name,role,is_active) VALUES(1,'Pessoa','Diretor',1)")
        if target in {'currency','policy'}:conn.exec_driver_sql("INSERT INTO tesseract_financeiro_currency VALUES('BRL','Real',2)")
        if target=='policy':conn.exec_driver_sql("INSERT INTO tesseract_financeiro_monetary_policy(organization_code,currency_code,decimal_places,rounding,created_at) VALUES('A','BRL',2,'HALF_UP','2026-10-07')")
        before=set(sa.inspect(conn).get_table_names())
        with pytest.raises(RuntimeError,match='preserv'):new.downgrade()
        assert set(sa.inspect(conn).get_table_names())==before


def test_migration_accepts_create_all_current_schema(app,monkeypatch):
    with app.app_context(),db.engine.begin() as conn:
        monkeypatch.setattr(old,'op',operations(conn));monkeypatch.setattr(new,'op',operations(conn))
        old.upgrade();new.upgrade()


def test_migration_rejects_wrong_new_table_before_any_ddl(monkeypatch):
    engine=sa.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        monkeypatch.setattr(old,'op',operations(conn));monkeypatch.setattr(new,'op',operations(conn));old.upgrade()
        conn.exec_driver_sql('CREATE TABLE tesseract_financeiro_currency(code TEXT PRIMARY KEY)')
        with pytest.raises(RuntimeError,match='incompatível'):new.upgrade()
        assert len(sa.inspect(conn).get_columns('tesseract_organization'))==6
        assert 'tesseract_organization_contact' not in sa.inspect(conn).get_table_names()


@pytest.mark.parametrize('target,operation',[('currency','update'),('currency','delete'),('policy','update'),('policy','delete')])
def test_configuration_immutable_through_orm(app,target,operation):
    with app.app_context():
        setup_policy()
        obj=db.session.get(Currency,'BRL') if target=='currency' else MonetaryPolicy.query.one()
        if operation=='delete': db.session.delete(obj)
        elif target=='currency':obj.decimal_places=3
        else:obj.rounding='HALF_EVEN'
        with pytest.raises(ValueError,match='imutável'): db.session.commit()
        db.session.rollback()
        assert resolve_policy('A')['rounding']=='HALF_UP'
        assert db.session.get(Currency,'BRL').decimal_places==2


def test_regular_user_denied_finance_and_contact_writes(app,client):
    from model.core.user import User
    with app.app_context():
        user=User(username='regular',email='regular@test.local',nome='Regular',nome_completo='Regular',celular='11999999999',is_admin=False,is_active=True)
        user.set_password('senha123');db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json={'username':'regular','password':'senha123'})
    assert client.get('/financeiro/').status_code==403
    assert client.post('/api/financeiro/currencies',json={'code':'BRL','name':'Real','decimal_places':2}).status_code==403
    assert client.post('/api/financeiro/policies',json={}).status_code==403
    assert client.post('/api/admin/organizations/1/contacts',json={}).status_code==403
    # CEP is auxiliary public address data, available to any authenticated user.
    app.extensions['getcep_provider'].transport=lambda *a,**kw:Response()
    assert client.get('/api/plugins/getcep/01001000').status_code==200


@pytest.mark.parametrize('manifest,entry',[
 ({'name':'bad','type':'addon'},''),
 ({'name':'bad','type':'plugin','table_prefix':'bad'},''),
 ({'name':'bad','type':'plugin','features':[]},''),
 ({'name':'bad','type':'plugin','requires':['missing']},''),
 ({'name':'bad','type':'plugin'},"__module__='Bad'\nclass Bad:pass\n"),
 ({'name':'bad','type':'plugin','label':'Bad','version':'1.0.0'},"from core.plugin_base import PluginBase\n__module__='Bad'\nclass Bad(PluginBase):\n def register_models(self):return []\n"),
])
def test_plugin_discovery_rejects_invalid_classification(tmp_path,manifest,entry):
    from core.module_manager import ModuleManager
    from flask import Flask
    directory=tmp_path/'plugin_bad';directory.mkdir()
    (directory/'plugin.json').write_text(json.dumps(manifest));(directory/'plugin.py').write_text(entry)
    manager=ModuleManager(Flask(__name__))
    with pytest.raises(ValueError):manager.discover_and_register_plugins(tmp_path)
    assert not manager._registered_modules
