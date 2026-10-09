"""Catálogo imutável, isolamento, autenticação e arquivamento otimista."""
import uuid
import pytest
from model.core.user import User
from tests.test_reports_workspace import app, client, create, read, save, post


def make_block(client):
    obj=create(client);value=read(client,obj['id'])
    value['layout']={'schema_version':1,'body':[{'id':'group','type':'section','props':{'columns':2},'children':[{'id':'text','type':'text','props':{'text':'Original','style':{'bold':True},'format':{'kind':'raw'}}}]}]}
    assert save(client,obj['id'],value).status_code==200
    payload={'key':'block.'+uuid.uuid4().hex,'name':'Cabeçalho','template_id':obj['id'],'version':1,'node_id':'group'}
    response=post(client,'/blocks',payload)
    assert response.status_code==201
    return obj,response.json['item'],payload


def test_snapshot_is_independent_and_archive_does_not_change_template(client):
    obj,block,_=make_block(client)
    assert block['id'] in [item['id'] for item in client.get('/api/reports/blocks').json['items']]
    assert 'node' not in block
    original=client.get(f"/api/reports/blocks/{block['id']}").json['item']
    value=read(client,obj['id']);value['layout']['body'][0]['children'][0]['props']['text']='Alterado'
    assert save(client,obj['id'],value).status_code==200
    assert client.get(f"/api/reports/blocks/{block['id']}").json['item']['node']==original['node']
    assert client.delete(f"/api/reports/blocks/{block['id']}",json={'lock_version':0},headers=client.report_headers).status_code==409
    assert client.delete(f"/api/reports/blocks/{block['id']}",json={'lock_version':1},headers=client.report_headers).status_code==200
    assert client.get(f"/api/reports/blocks/{block['id']}").status_code==404
    assert read(client,obj['id'])['layout']==value['layout']


def test_unique_key_and_published_source(client):
    obj,block,payload=make_block(client)
    assert post(client,'/blocks',payload).status_code==409
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    payload['key']='block.'+uuid.uuid4().hex
    assert post(client,'/blocks',payload).status_code==201
    assert client.put(f"/api/reports/blocks/{block['id']}",json={},headers=client.report_headers).status_code==405


def test_auth_csrf_and_permissions(client,app,monkeypatch):
    obj,block,payload=make_block(client)
    assert app.test_client().get('/api/reports/blocks').status_code==401
    assert client.post('/api/reports/blocks',json=payload).status_code==403
    monkeypatch.setattr(User,'has_permission',lambda self,name:name=='report_templates.list')
    assert client.get('/api/reports/blocks').status_code==200
    assert client.get(f"/api/reports/blocks/{block['id']}").status_code==403
    assert post(client,'/blocks',payload).status_code==403
    assert client.delete(f"/api/reports/blocks/{block['id']}",json={'lock_version':1},headers=client.report_headers).status_code==403


@pytest.mark.parametrize('change',[{'template_id':True},{'version':0},{'name':''},{'key':'bad key'},{'node_id':'missing'}])
def test_invalid_capture_rejected(client,change):
    obj=create(client);value=read(client,obj['id'])
    payload={'key':'block.'+uuid.uuid4().hex,'name':'Bloco','template_id':obj['id'],'version':1,'node_id':value['layout']['body'][0]['id'],**change}
    assert post(client,'/blocks',payload).status_code in (422,404)
