"""Workspace integrado: contexto, composição financeira e operações reais."""
from urllib.parse import urlparse,parse_qs
from decimal import Decimal
import pytest
from tests.test_financeiro_treasury import app,client,setup,title,payment,ok,DATE,_login_admin
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction
from addons.addon_financeiro.root.services import treasury_service as t,workspace_service as s,cash_operations_service as operations
from addons.addon_financeiro.root.controller.workspace import VIEWS


def options(**extra): return {'organization_code':'A','date_from':'2026-10-01','date_to':'2026-10-31',**extra}


def test_dashboard_exact_dates_internal_transfers_reversal_and_pending(app):
    with app.app_context():
        data=setup(); other=setup(code='B',opening='999')
        destination=ok(t.create_catalog('accounts',{'organization_code':'A','name':'Caixa','kind':'CASH','opening_balance':'0','opening_date':DATE,'policy_version_id':None},actor='admin'))
        ok(operations.transfer({'organization_code':'A','source_account_id':data[0]['id'],'destination_account_id':destination['id'],'amount':'100',
            'operation_date':DATE,'policy_version_id':None,'idempotency_key':'TRANSFER','notes':None},actor='admin'))
        payable=ok(t.create_title(title(data,total='100.01'),actor='admin'))
        payment1=ok(t.settle(payable['installments'][0]['id'],payment(data,principal='40',interest='1'),actor='admin'))
        receivable=ok(t.create_title(title(data,kind='RECEIVABLE',key='IN',total='200'),actor='admin'))
        ok(t.settle(receivable['installments'][0]['id'],payment(data,principal='50',key='IN'),actor='admin'))
        value=s.dashboard(options())
        assert value['balance']=='1009'
        assert value['income']=='50' and value['outflow']=='41' and value['net']=='9'
        assert value['pending']=={'PAYABLE':'60.01','RECEIVABLE':'150'}
        assert value['categories']==[{'id':data[1]['id'],'name':'Compras','amount':'41'}]
        assert sum(Decimal(a['balance']) for a in value['accounts'])==1009
        assert value['windows']['7']['PAYABLE']=='60.01'
        assert value['monthly']==[{'month':'2026-10','income':'50','outflow':'41'}]
        ok(t.reverse(payment1['id'],{'operation_date':DATE,'reason':'Correção','idempotency_key':'R1'},actor='admin'))
        value=s.dashboard(options())
        assert value['balance']=='1050' and value['categories'][0]['amount']=='0'
        assert value['pending']['PAYABLE']=='100.01'
        with pytest.raises(ValueError):s.dashboard(options(account_id=other[0]['id']))


@pytest.mark.parametrize('key',[key for key in VIEWS if key[1]!='detail'])
def test_views_render_same_shell_without_iframes(client,app,key):
    _login_admin(app,client)
    with app.app_context():setup()
    response=client.get('/financeiro/',query_string=options(tab=key[0],view=key[1]))
    assert response.status_code==200,response.data.decode()[:3000]
    html=response.data.decode()
    assert 'id="finance-workspace"' in html and 'financeiro_workspace.js' in html
    assert 'aria-label="Áreas financeiras"' in html and '<iframe' not in html
    assert 'DRE e resultados' in html


def test_context_survives_navigation_posts_errors_and_organization_change(client,app):
    _login_admin(app,client)
    with app.app_context():
        data=setup();setup(code='B')
        item=ok(t.create_title(title(data),actor='admin'))
    query=options(tab='titles',view='detail',title_id=item['id'])
    response=client.get('/financeiro/',query_string=query)
    assert response.status_code==200
    assert 'Registrar pagamento' in response.data.decode()
    response=client.post('/financeiro/liquidacoes/parcelas/'+str(item['installments'][0]['id'])+'/baixar',query_string=options(),data={key:('' if value is None else value) for key,value in payment(data).items()})
    assert response.status_code==302
    location=parse_qs(urlparse(response.location).query)
    assert location['tab']==['titles'] and location['view']==['detail'] and location['organization_code']==['A']
    assert location['date_from']==['2026-10-01']
    assert client.get(response.location).status_code==200
    bad=client.post('/financeiro/titulos/',query_string=options(),data={'organization_code':'A','reference':'Preservar digitado'})
    assert bad.status_code==422 and b'Preservar digitado' in bad.data and b'id="finance-workspace"' in bad.data
    context=client.get('/financeiro/',query_string={'tab':'cash','view':'accounts'})
    assert b'value="A" selected' in context.data
    assert client.get('/financeiro/',query_string=options(tab='titles',view='detail',title_id=item['id'],organization_code='B')).status_code==404
    assert client.get('/financeiro/titulos/'+str(item['id']),query_string={'organization_code':'B'}).status_code==404


def test_title_dashboard_filters_and_monthly_movements(client,app):
    _login_admin(app,client)
    with app.app_context():
        data=setup()
        item=ok(t.create_title(title(data,reference='VENCIDO',first_due='2026-10-17'),actor='admin'))
        ok(t.create_title(title(data,reference='FUTURO',first_due='2026-11-03',key='NEXT'),actor='admin'))
        paid=ok(t.create_title(title(data,reference='PAGO',key='PAID'),actor='admin'))
        ok(t.settle(paid['installments'][0]['id'],payment(data),actor='admin'))
    response=client.get('/financeiro/',query_string=options(tab='titles',view='list',scope='overdue'))
    assert response.status_code==200
    assert b'VENCIDO' in response.data and b'FUTURO' not in response.data and b'PAGO' not in response.data
    response=client.get('/financeiro/',query_string=options(tab='titles',view='list',scope='upcoming',days='7'))
    assert b'FUTURO' in response.data and b'VENCIDO' not in response.data
    response=client.get('/financeiro/',query_string=options(tab='cash',view='movements',source='operating',direction='out'))
    assert response.status_code==200 and b'settlement:' in response.data and b'opening:' not in response.data


def test_workspace_access_source_permissions_and_automatic_menu(client,app,monkeypatch):
    _login_admin(app,client)
    with app.app_context():
        setup()
        module=app.module_manager._registered_modules['financeiro']
        from core.module_base import ModuleBase
        assert type(module).get_transactions is ModuleBase.get_transactions
        entries=Transaction.query.filter_by(source_module='financeiro',is_active=True).filter(Transaction.route.isnot(None)).all()
        assert [(tx.code,tx.route) for tx in entries]==[('TX_WORKSPACE_FINANCEIRO','/financeiro/')]
        assert Transaction.query.filter_by(code='TX_GROUP_REPORTS_FINANCEIRO').one().is_active is False
        app.module_manager.sync_all_transactions()
        assert Transaction.query.filter_by(code='TX_WORKSPACE_FINANCEIRO').count()==1
    monkeypatch.setattr(User,'has_permission',lambda self,key:key=='financial_titles.list')
    response=client.get('/financeiro/')
    assert response.status_code==200 and b'data-tab="titles"' in response.data
    assert 'Visão geral'.encode() not in response.data and b'Caixa e bancos' not in response.data
    assert client.get('/financeiro/',query_string=options(tab='overview')).status_code==403
    assert client.get('/financeiro/',query_string=options(tab='reconciliation')).status_code==403
    monkeypatch.setattr(User,'has_permission',lambda self,key:False)
    assert client.get('/financeiro/').status_code==403
    assert app.test_client().get('/financeiro/').status_code in (302,401)


def test_dashboard_and_workspace_reads_do_not_mutate_money(app,client):
    import sqlalchemy as sa
    _login_admin(app,client)
    with app.app_context():
        data=setup();ok(t.create_title(title(data),actor='admin'))
        before=(t.Title.query.count(),t.Movement.query.count(),db.session.get(t.Account,data[0]['id']).balance)
        statements=[]
        def track(connection,cursor,statement,parameters,context,executemany):statements.append(statement.strip().split()[0].upper())
        sa.event.listen(db.engine,'before_cursor_execute',track)
        try:s.dashboard(options())
        finally:sa.event.remove(db.engine,'before_cursor_execute',track)
        assert set(statements)<={'SELECT'}
        assert before==(t.Title.query.count(),t.Movement.query.count(),db.session.get(t.Account,data[0]['id']).balance)
    assert client.get('/financeiro/',query_string=options(date_to='2028-01-01')).status_code==422
    assert client.get('/financeiro/',query_string=options(organization_code='INEXISTENTE')).status_code==422
    assert client.get('/financeiro/',query_string=options(tab='unknown')).status_code==404


def test_workspace_forms_target_real_operations_and_themes(client,app):
    import re
    from html import unescape
    _login_admin(app,client)
    with app.app_context():setup()
    for tab,view,expected in [('titles','list','/financeiro/titulos/'),('cash','accounts','/financeiro/contas/'),('cash','transfers','/financeiro/transferencias/'),('settings','rates','/financeiro/exchange-rates/'),('settings','conversions','/financeiro/conversions/'),('settings','versions','/financeiro/policy-versions/')]:
        response=client.get('/financeiro/',query_string=options(tab=tab,view=view))
        html=response.data.decode()
        actions=[urlparse(unescape(action)).path for action in re.findall(r'<form[^>]*method="post"[^>]*action="([^"]+)"',html)]
        assert expected in actions,(view,actions)
        assert '/financeiro/' not in actions
    for theme in ('dark','light'):
        assert client.post('/api/auth/update-theme',json={'theme':theme}).json['success']
        response=client.get('/financeiro/',query_string=options())
        assert f'data-theme="{theme}"'.encode() in response.data
        assert b'finance-dashboard-data' in response.data
        assert (b'id="theme-dark-css"' in response.data)==(theme=='dark')


def test_pagination_preserves_due_scope_and_context(client,app):
    _login_admin(app,client)
    with app.app_context():
        data=setup()
        for i in range(21):ok(t.create_title(title(data,key='PAGE-'+str(i),reference='DOC-'+str(i),first_due='2026-10-17'),actor='admin'))
    response=client.get('/financeiro/',query_string=options(tab='titles',view='list',scope='overdue',kind='PAYABLE'))
    assert response.status_code==200
    html=response.data.decode()
    assert 'scope=overdue' in html and 'kind=PAYABLE' in html and 'page=2' in html and 'date_from=2026-10-01' in html
