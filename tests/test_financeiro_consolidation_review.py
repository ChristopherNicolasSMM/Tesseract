"""Regressões de navegação, consultas independentes e evidência de fechamento."""
import hashlib
import copy
import pytest
import sqlalchemy as sa
from tests.test_financeiro_accrual import app,client,setup,options,_login_admin
from tests.test_financeiro_result_closing import recognized,closing
from addons.addon_financeiro.root.services import accrual_service as a,treasury_service as t,result_closing_service as c
from core.db import db


def test_costs_and_entries_are_not_blocked_by_unrelated_large_category_catalog(app,client):
    _login_admin(app,client)
    with app.app_context():
        data=setup();recognized(data)
        db.session.execute(sa.insert(t.Category),[{'organization_code':'A','name':f'Categoria extra {i}','direction':'PAYABLE','created_by':'admin'} for i in range(2000)])
        db.session.commit()
    for view in ('costs','entries'):
        response=client.get('/financeiro/',query_string=options(tab='results',view=view))
        assert response.status_code==200,response.data.decode()[:2000]
    assert b'title:' in response.data


def test_result_views_do_not_load_unrelated_entry_history_and_dashboard_is_reachable(app,client):
    _login_admin(app,client)
    with app.app_context():
        data=setup();recognized(data)
        engine=db.engine;queries=[]
    def track(connection,cursor,statement,parameters,context,executemany):queries.append(statement)
    sa.event.listen(engine,'before_cursor_execute',track)
    try:
        for view in ('dashboard','dre','review','costs','closing','classifications'):
            queries.clear()
            response=client.get('/financeiro/',query_string=options(tab='results',view=view))
            assert response.status_code==200,response.data.decode()[:2000]
            assert not any('count(' in sql.lower() and 'tesseract_financeiro_accrual_entry' in sql for sql in queries),queries
            assert 'Dashboard de resultados'.encode() in response.data
    finally:sa.event.remove(engine,'before_cursor_execute',track)


def test_invalid_global_context_is_rejected_consistently_and_does_not_poison_session(app,client):
    _login_admin(app,client)
    with app.app_context():setup()
    for view in ('dashboard','dre','review','costs','closing','classifications','entries'):
        response=client.get('/financeiro/',query_string=options(tab='results',view=view,date_from='invalido'))
        assert response.status_code==422,response.data.decode()[:2000]
    response=client.get('/financeiro/',query_string=options(tab='results',view='closing',period='2026-99'))
    assert response.status_code==422
    assert client.get('/financeiro/',query_string=options(tab='results',view='closing')).status_code==200
    with app.app_context():assert c.Close.query.count()==0


def test_closure_export_is_scoped_readonly_and_preserves_reopened_snapshot(app,client,monkeypatch):
    from model.core.user import User
    _login_admin(app,client)
    with app.app_context():
        data=setup();recognized(data);setup(code='B')
        result=c.close(closing(),actor='admin');assert result.success
        closed=result.data
        reopened=c.reopen(closed['id'],{'reason':'Revisão','idempotency_key':'OPEN'},actor='admin');assert reopened.success
        engine=db.engine;queries=[]
    def track(connection,cursor,statement,parameters,context,executemany):queries.append(statement.strip().split()[0].upper())
    url=f"/api/financeiro/results/closures/{closed['id']}"
    sa.event.listen(engine,'before_cursor_execute',track)
    try:
        response=client.get(url,query_string={'organization_code':'A'})
    finally:sa.event.remove(engine,'before_cursor_execute',track)
    assert response.status_code==200,response.json
    value=response.json['item']
    assert value['status']=='REOPENED' and value['snapshot']==closed['snapshot']
    assert value['integrity']['valid'] is True
    assert value['digest']==hashlib.sha256(t.dump(value['snapshot']).encode('utf-8')).hexdigest()
    assert response.headers['Cache-Control']=='no-store'
    assert set(queries)=={'SELECT'}
    assert client.get(url,query_string={'organization_code':'B'}).status_code==404
    assert client.get(url).status_code==422
    assert client.get(url,query_string={'organization_code':'A','unexpected':'x'}).status_code==422
    page=client.get('/financeiro/',query_string=options(tab='results',view='closing'))
    assert page.status_code==200 and b'Exportar registro de fechamento' in page.data
    monkeypatch.setattr(User,'has_permission',lambda self,key:key!='financial_results.list')
    assert client.get(url,query_string={'organization_code':'A'}).status_code==403


@pytest.mark.parametrize('field',['digest','snapshot'])
def test_closure_integrity_divergence_is_visible_without_rewriting_evidence(app,client,field):
    _login_admin(app,client)
    with app.app_context():
        data=setup();recognized(data);result=c.close(closing(),actor='admin');assert result.success
        row_id=result.data['id'];original=result.data['snapshot']
        altered=copy.deepcopy(original)
        altered['statement']['rows'][0]['total']='123'
        expected_snapshot=altered if field=='snapshot' else original
        expected_digest='0'*64 if field=='digest' else result.data['digest']
        changes={'digest':expected_digest} if field=='digest' else {'snapshot_json':t.dump(altered)}
        db.session.execute(sa.update(c.Close).where(c.Close.id==row_id).values(**changes));db.session.commit();db.session.expire_all()
    response=client.get(f'/api/financeiro/results/closures/{row_id}',query_string={'organization_code':'A'})
    assert response.status_code==200
    assert response.json['item']['integrity']['valid'] is False
    assert response.json['item']['digest']==expected_digest and response.json['item']['snapshot']==expected_snapshot
    page=client.get('/financeiro/',query_string=options(tab='results',view='closing'))
    assert page.status_code==200 and b'Integridade divergente' in page.data
    with app.app_context():assert db.session.get(c.Close,row_id).digest==expected_digest
