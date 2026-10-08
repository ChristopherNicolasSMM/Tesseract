"""Regressões dos problemas comunicados após a entrega inicial."""
import pytest
from tests.test_admin_users_pages import app, client, _login_admin
from core.db import db
from model.core.organization import Organization
from model.core.transaction import Transaction
from services.core.organization_service import save_organization, save_organization_contact, resolve_organization
from core.module_base import ModuleBase
from core.addon_base import AddonBase


def test_failed_create_keeps_every_posted_profile_field(app, client):
    _login_admin(app, client)
    data={'code':'NEW','name':'Nome digitado','legal_name':'Razão digitada','trade_name':'Fantasia',
          'cnpj':'12.ABC.345/01DE-35','email':'inválido','phone':'11999999999','website':'https://example.test',
          'cep':'01001-000','logradouro':'Praça da Sé','numero':'42','complemento':'Sala 2',
          'bairro':'Sé','cidade':'São Paulo','estado':'SP','pais':'Brasil','state_registration':'ISENTO',
          'municipal_registration':'ABC','_active_present':'1','is_active':'on'}
    response=client.post('/admin/organizations/',data=data)
    assert response.status_code==422 and b'role="alert"' in response.data
    for field,value in data.items():
        if field not in {'_active_present','is_active'}:
            assert value.encode() in response.data,field
    assert b'collapse show' in response.data
    with app.app_context():assert Organization.query.count()==0


def test_edit_form_errors_keep_unsaved_values_but_db_unchanged(app,client):
    _login_admin(app,client)
    with app.app_context():
        ident=save_organization({'code':'ORG','name':'Original','legal_name':'Persistida','email':'old@test.local','is_active':True}).data['id']
    response=client.post(f'/admin/organizations/{ident}',data={'name':'Digitado','legal_name':'Nova razão','email':'bad','_active_present':'1'})
    assert response.status_code==422 and 'Nova razão'.encode() in response.data
    assert b'value="bad"' in response.data
    with app.app_context():
        record=resolve_organization(ident)
        assert record['name']=='Original' and record['legal_name']=='Persistida' and record['is_active'] is True
    response=client.post(f'/admin/organizations/{ident}',data={'name':'Salvo','legal_name':'Nova razão','email':'new@test.local','_active_present':'1'})
    assert response.status_code==302 and response.headers['Location'].endswith(f'/{ident}')
    with app.app_context():
        record=resolve_organization(ident,require_active=False)
        assert record['name']=='Salvo' and record['legal_name']=='Nova razão' and record['is_active'] is False


def test_partial_form_preserves_omitted_profile_and_state(app,client):
    _login_admin(app,client)
    with app.app_context():ident=save_organization({'code':'ORG','name':'A','legal_name':'Razão','email':'org@test.local','is_active':True}).data['id']
    assert client.post(f'/admin/organizations/{ident}',data={'name':'B'}).status_code==302
    with app.app_context():
        record=resolve_organization(ident)
        assert record['name']=='B' and record['legal_name']=='Razão' and record['email']=='org@test.local'


def test_responsible_validation_keeps_inputs_and_preserves_database(app,client):
    _login_admin(app,client)
    with app.app_context():
        ident=save_organization({'code':'ORG','name':'A'}).data['id']
        contact=save_organization_contact(ident,{'name':'Pessoa','role':'Diretor','email':'person@test.local'}).data['id']
    response=client.post(f'/admin/organizations/{ident}/contacts/{contact}',data={'name':'Digitado','role':'Gerente','cpf':'wrong','_active_present':'1','is_active':'on'})
    assert response.status_code==422 and b'value="Digitado"' in response.data and b'value="wrong"' in response.data
    assert f'contact-{ident}-{contact}-name'.encode() in response.data
    with app.app_context():assert resolve_organization(ident)['contacts'][0]['name']=='Pessoa'
    assert client.post(f'/admin/organizations/{ident}/contacts/{contact}',data={'role':'Alterada'}).status_code==302
    with app.app_context():
        c=resolve_organization(ident)['contacts'][0]
        assert c['is_active'] is True and c['email']=='person@test.local'


def test_list_toolbar_pagination_exports_and_detail_separation(app,client):
    _login_admin(app,client)
    with app.app_context():
        for index in range(21):assert save_organization({'code':f'ORG{index:02}','name':f'Empresa {index:02}'}).success
    page=client.get('/admin/organizations/').data
    assert b'table table-striped' in page and b'pagination pagination-sm' in page
    assert b'Ver / Editar' in page and b'export.csv' in page and b'export.xlsx' in page
    assert page.count(b'name="legal_name"')==1  # novo form; nenhum edit inline na tabela
    assert b'Empresa 20' in client.get('/admin/organizations/?page=2').data
    csv=client.get('/admin/organizations/export.csv?q=ORG20')
    assert csv.status_code==200 and b'ORG20' in csv.data and b'ORG00' not in csv.data
    assert client.get('/admin/organizations/export.xlsx?q=ORG20').status_code==200
    assert client.get('/admin/organizations/?page=-1').status_code==200


def test_menu_uses_defaults_and_retires_only_own_obsolete_leaf(app):
    with app.app_context():
        module=app.module_manager._registered_modules['financeiro']
        assert type(module).get_transactions is ModuleBase.get_transactions
        assert type(module).register_routes is ModuleBase.register_routes
        assert type(module).register_models is AddonBase.register_models
        for code,source in [('FIN_SETUP','financeiro'),('OTHER','estoque')]:
            db.session.add(Transaction(code=code,label=code,route='/financeiro/',source_module=source,is_active=True))
        db.session.commit()
        app.module_manager.sync_all_transactions()
        assert Transaction.query.filter_by(code='FIN_SETUP').one().is_active is False
        assert Transaction.query.filter_by(code='OTHER').one().is_active is True
        folder=Transaction.query.filter_by(code='TX_GROUP_AUTO_FINANCEIRO').one()
        assert folder.route is None
        leaves=Transaction.query.filter_by(parent_id=folder.id).all()
        assert {t.code for t in leaves}=={'TX_AUTO_CURRENCIES','TX_AUTO_MONETARY_POLICIES','TX_AUTO_EXCHANGE_RATES','TX_AUTO_MONETARY_CONVERSIONS','TX_AUTO_POLICY_VERSIONS'}
        assert {t.route for t in leaves}=={'/financeiro/currencies/','/financeiro/monetary-policies/','/financeiro/exchange-rates/','/financeiro/conversions/','/financeiro/policy-versions/'}
        app.module_manager.sync_all_transactions()
        assert Transaction.query.filter_by(code='TX_GROUP_AUTO_FINANCEIRO').count()==1


def test_financial_invalid_post_keeps_values_and_no_writes(app,client):
    _login_admin(app,client)
    response=client.post('/financeiro/currencies',data={'code':'BRL','name':'Real digitado','decimal_places':'7'})
    assert response.status_code==422 and b'value="Real digitado"' in response.data
    assert b'value="7"' in response.data and b'role="alert"' in response.data
    assert client.get('/api/financeiro/currencies').get_json()['items']==[]


def test_cep_markup_reports_missing_initialization_and_prefix(app,client):
    _login_admin(app,client)
    page=client.get('/admin/organizations/').data
    assert b'/plugins/getcep/static/getcep.js?v=1.0.1' in page
    assert client.get('/plugins/getcep/static/getcep.js?v=1.0.1').mimetype in {'text/javascript','application/javascript'}
    assert b'data-getcep-button disabled' in page
    assert 'ainda não inicializada'.encode() in page
    assert b'data-getcep-url="/api/plugins/getcep/__CEP__"' in page
    with app.test_request_context('/admin/organizations/',environ_overrides={'SCRIPT_NAME':'/tesseract'}):
        context={};app.update_template_context(context)
        assert context['getcep_lookup_url']=='/tesseract/api/plugins/getcep/__CEP__'
