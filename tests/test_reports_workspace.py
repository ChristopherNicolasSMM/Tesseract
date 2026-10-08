"""Persistência real, autorização, concorrência e composição do addon."""
import uuid
import pytest
from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_reports.root.services import report_template_service as svc
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, ReportError
from addons.addon_reports.root.services.report_pdf_service import render_pdf
from addons.addon_reports.root.model.report_template_version import ReportTemplateVersion


@pytest.fixture(scope='module')
def app():
    return create_app(env='testing')


@pytest.fixture
def client(app):
    client = app.test_client()
    with app.app_context():
        username = 'reports_' + uuid.uuid4().hex[:8]
        user = User(username=username, email=username+'@test.local', nome='Teste', nome_completo='Teste', celular='11999999999', is_admin=True, is_active=True)
        user.set_password('test-password')
        db.session.add(user)
        db.session.commit()
    client.post('/api/auth/login', json={'username':username,'password':'test-password'})
    assert client.get('/reports/').status_code == 200
    with client.session_transaction() as session:
        client.report_headers = {'X-Reports-CSRF':session['reports_csrf']}
    return client


def post(client, path, data):
    return client.post('/api/reports'+path, json=data, headers=client.report_headers)


def create(client):
    response=post(client,'/templates',{'key':'test.'+uuid.uuid4().hex,'name':'Teste'})
    assert response.status_code == 201
    return response.json['item']


def read(client, ident, number=1):
    response=client.get(f'/api/reports/templates/{ident}/versions/{number}')
    assert response.status_code == 200
    return response.json['item']


def save(client, ident, value):
    payload={k:value[k] for k in ('lock_version','layout','data_schema','sample_data','parameters')}
    return client.put(f'/api/reports/templates/{ident}/versions/1',json=payload,headers=client.report_headers)


def test_models_registered_with_prefix_and_workspace_uses_base(client, app):
    with app.app_context():
        assert ReportTemplateVersion.__table__.name == 'tesseract_reports_report_template_version'
    response=client.get('/reports/')
    assert b'reports_editor.js' in response.data
    assert b'nav-tabs-bordered' in response.data
    assert '<h1>Relatórios</h1>' in response.data.decode()


def test_unauthenticated_and_csrf_blocked(app, client):
    anonymous=app.test_client()
    assert anonymous.get('/api/reports/templates').status_code == 401
    assert client.post('/api/reports/templates',json={'key':'no.csrf','name':'No'}).status_code == 403


def test_non_admin_without_permissions_cannot_list(app):
    client=app.test_client()
    with app.app_context():
        username='viewer'+uuid.uuid4().hex
        user=User(username=username,email=username+'@test.local',nome='Viewer',nome_completo='Viewer',celular='11999999999',is_active=True)
        user.set_password('password');db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json={'username':username,'password':'password'})
    assert client.get('/api/reports/templates').status_code == 403


def test_save_reloads_and_stale_write_rejected(client):
    obj=create(client); value=read(client,obj['id']); value['layout']['body'][0]['props']['text']='Persistido'
    assert save(client,obj['id'],value).status_code == 200
    assert read(client,obj['id'])['layout']['body'][0]['props']['text']=='Persistido'
    assert save(client,obj['id'],value).status_code == 409
    assert read(client,obj['id'])['lock_version']==2


def test_publish_freezes_and_clone_preserves_old_content(client):
    obj=create(client)
    response=post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':1})
    assert response.status_code == 200
    published=read(client,obj['id']);assert published['status']=='published';assert len(published['content_hash'])==64
    assert save(client,obj['id'],published).status_code==409
    clone=post(client,f"/templates/{obj['id']}/versions/1/clone",{})
    assert clone.status_code==201
    assert read(client,obj['id'],2)['status']=='draft'
    assert read(client,obj['id'])['status']=='published'


def test_parameters_persist_defaults_and_reject_invalid_data(client):
    obj=create(client);value=read(client,obj['id'])
    value['parameters']=[{'key':'title','label':'Título','schema':{'type':'string'},'required':True,'default':'Default'}]
    value['layout']['body'][0]['props']={'binding':{'source':'parameters','path':['title']}}
    assert save(client,obj['id'],value).status_code==200
    preview=post(client,f"/templates/{obj['id']}/versions/1/preview",{'format':'html'})
    assert preview.status_code==200;assert '<p>Default</p>' in preview.json['html']
    invalid=post(client,f"/templates/{obj['id']}/versions/1/preview",{'format':'html','parameters':{'title':5}})
    assert invalid.status_code==422


def test_published_only_render_and_contract_validation(client):
    obj=create(client)
    assert post(client,'/render',{'template':obj['key'],'data':{}}).status_code==404
    value=read(client,obj['id']);value['data_schema']={'type':'object','required':['name'],'properties':{'name':{'type':'string'}},'additionalProperties':False};value['sample_data']={'name':'Valid'}
    assert save(client,obj['id'],value).status_code==200
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    assert post(client,'/render',{'template':obj['key'],'data':{}}).status_code==422
    pdf=post(client,'/render',{'template':obj['key'],'data':{'name':'Valid'}})
    assert pdf.status_code==200;assert pdf.data.startswith(b'%PDF-');assert pdf.headers['Cache-Control']=='no-store'


def test_schema_remote_reference_rejected(client):
    obj=create(client);value=read(client,obj['id']);value['data_schema']={'$ref':'http://127.0.0.1/private'}
    assert save(client,obj['id'],value).status_code==422


def test_text_escape_and_table_item_scope():
    layout={'schema_version':1,'body':[{'id':'table','type':'table','props':{'collection':{'source':'data','path':['items']},'columns':[{'label':'Descrição','binding':{'source':'item','path':['name']}}]}}]}
    html=ReportLayoutService.render(layout,{'items':[{'name':'<script>alert(1)</script>{{ secret }}'}]}, {})
    assert '&lt;script&gt;' in html;assert '<script>' not in html;assert '{{ secret }}' in html
    with pytest.raises(ReportError):ReportLayoutService.render(layout,{'items':[{}]}, {})


def test_long_table_real_pdf(app):
    layout={'schema_version':1,'body':[{'id':'table','type':'table','props':{'collection':{'source':'data','path':['items']},'columns':[{'label':'Nome','binding':{'source':'item','path':['name']}}]}}]}
    html=ReportLayoutService.render(layout,{'items':[{'name':f'Linha {i} — acentuação'} for i in range(150)]},{})
    with app.app_context():
        pdf=render_pdf(html)
    assert pdf.startswith(b'%PDF-')
    assert b'/Type /Pages' in pdf or len(pdf)>5000


def test_internal_service_requires_authorized_context(app):
    with app.test_request_context():
        with pytest.raises(ReportError) as exc:svc.list_templates()
        assert exc.value.status==401


def test_invalid_layout_does_not_raise_unstructured_error(client):
    obj=create(client)
    for malformed in ([{'id':'x','type':[], 'props':{}}], [{'id':'x','type':'text','props':{'text':'one'}},{'id':'x','type':'text','props':{'text':'two'}}]):
        value=read(client,obj['id']);value['layout']['body']=malformed
        result=save(client,obj['id'],value)
        assert result.status_code==422
        assert result.json['error']['code']=='reports.error.layout'


def test_pdf_timeout_releases_capacity(app, monkeypatch):
    import subprocess
    from addons.addon_reports.root.services import report_pdf_service as pdf
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(pdf.subprocess, 'run', timeout)
    with app.app_context():
        for _ in range(3):
            with pytest.raises(ReportError) as error:pdf.render_pdf('<html></html>')
            assert error.value.code=='reports.error.pdf'


def test_worker_blocks_external_and_local_resources():
    from addons.addon_reports.root.services.report_pdf_worker import blocked_fetcher
    for resource in ('file:///etc/passwd','http://127.0.0.1/private','https://example.com/logo.png'):
        with pytest.raises(ValueError):blocked_fetcher(resource)


def test_session_token_available_without_catalog_permission(app):
    client=app.test_client()
    with app.app_context():
        username='token'+uuid.uuid4().hex
        user=User(username=username,email=username+'@test.local',nome='Token',nome_completo='Token',celular='11999999999',is_active=True)
        user.set_password('password');db.session.add(user);db.session.commit()
    client.post('/api/auth/login',json={'username':username,'password':'password'})
    token=client.get('/api/reports/session')
    assert token.status_code==200 and len(token.json['csrf_token'])>=32
    assert client.get('/api/reports/templates').status_code==403


def test_generation_does_not_discard_pending_business_changes(app):
    from flask_login import login_user
    from addons.addon_reports.root.model.report_template import ReportTemplate
    with app.test_request_context():
        user=User.query.filter_by(is_admin=True).first()
        login_user(user)
        pending=ReportTemplate(key='pending.'+uuid.uuid4().hex,name='Não descartar')
        db.session.add(pending)
        with pytest.raises(ReportError) as error:
            svc.generate_report('any.report',data={})
        assert error.value.code=='reports.error.transaction'
        assert pending in db.session.new
        db.session.rollback()
