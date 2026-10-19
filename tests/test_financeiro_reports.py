"""Relatórios financeiros consomem DTOs públicos, sem mutar a tesouraria."""
import uuid
import pytest
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction
from tests.test_reports_workspace import app,client,post
from tests.test_reports_emission import publish
from tests.test_financeiro_treasury import setup,title,payment,ok,DATE
from addons.addon_financeiro.root.services import treasury_service as t,cash_operations_service as operations
from addons.addon_financeiro.root.model.cash_operations import BankStatementLine as Line
from addons.addon_reports.root.services import report_library_service as library,report_emission_service as emission
from addons.addon_reports.root.services.report_layout_service import validate_data


@pytest.mark.parametrize('screen,kind',[('financeiro-fluxo-caixa','cash_flow'),('financeiro-titulos','titles'),('financeiro-liquidacoes','settlements'),('financeiro-conciliacao','reconciliation'),('financeiro-dre','dre'),('financeiro-resultados','results_dashboard')])
def test_public_data_published_html_segregation_and_readonly(client,app,screen,kind):
    code='F'+uuid.uuid4().hex[:12].upper()
    with app.app_context():
        data=setup(code=code); item=ok(t.create_title(title(data,reference='Nota financeira REAL'),actor='admin'))
        settled=ok(t.settle(item['installments'][0]['id'],payment(data),actor='admin'))
        ok(operations.import_statement({'account_id':data[0]['id'],'currency_code':'BRL','reference':'Extrato REAL','idempotency_key':'B1',
            'lines':[{'external_id':'EXT-REAL','operation_date':DATE,'amount':'-100','description':'Pagamento REAL'}]},actor='admin'))
        before=(db.session.get(t.Account,data[0]['id']).balance,t.Movement.query.count(),Line.query.count())
    opts={'organization_code':code,'date_from':DATE,'date_to':'2026-10-31'}
    response=post(client,'/examples/'+screen+'/data',{'options':opts})
    assert response.status_code==200,response.json
    value=response.json['item']
    validate_data(library.definition(screen)['data_schema'],value)
    assert value['contract']=='financeiro.'+kind+'.v1'
    assert value['organization_code']==code
    obj=publish(client,screen)
    body={'template':obj['key'],'version':1,'options':{'organization_code':code},'filters':{'date_from':DATE,'date_to':'2026-10-31'}}
    rendered=post(client,'/emission/'+screen,body)
    assert rendered.status_code==200,rendered.data.decode()[:3000]
    assert code in rendered.data.decode()
    assert post(client,'/emission/'+screen,{**body,'filters':{}}).status_code==422
    assert post(client,'/emission/'+screen,{**body,'filters':{'date_from':'2026-11-01','date_to':DATE}}).status_code==422
    with app.app_context():
        after=(db.session.get(t.Account,data[0]['id']).balance,t.Movement.query.count(),Line.query.count())
        assert before==after


def test_finance_report_menu_permissions_and_optional_addon(client,app,monkeypatch):
    with app.app_context():
        group=Transaction.query.filter_by(code='TX_GROUP_REPORTS_FINANCEIRO').one()
        assert group.parent.code=='TX_GROUP_AUTO_FINANCEIRO'
        for name,config in emission.SCREENS.items():
            if config[3]=='financeiro':
                entry=Transaction.query.filter_by(code='TX_REPORT_EMIT_'+name.upper().replace('-','_')).one()
                assert entry.parent_id==group.id
    monkeypatch.setattr(User,'has_permission',lambda self,key:key.startswith('report_templates.'))
    assert client.get('/api/reports/emission/financeiro-fluxo-caixa').status_code==403
    monkeypatch.setattr(User,'has_permission',lambda self,key:key!='financial_titles.list')
    assert client.get('/api/reports/emission/financeiro-fluxo-caixa').status_code==403
    assert client.get('/financeiro/fluxo-caixa/').status_code==403
    monkeypatch.undo()
    addon=app.module_manager._registered_modules.pop('financeiro')
    try: assert client.get('/api/reports/emission/financeiro-fluxo-caixa').status_code==503
    finally: app.module_manager._registered_modules['financeiro']=addon


@pytest.mark.parametrize('screen',['financeiro-dre','financeiro-resultados'])
def test_dre_report_renders_recognized_result_with_permission(client,app,monkeypatch,screen):
    from addons.addon_financeiro.root.services import accrual_service as accrual
    from tests.test_financeiro_accrual import classification,request
    code='D'+uuid.uuid4().hex[:12].upper()
    with app.app_context():
        data=setup(code=code);source=ok(t.create_title(title(data,total='100.01'),actor='admin'))
        c=ok(accrual.classify(classification(data),actor='admin'))
        ok(accrual.recognize(request(data,c,source),actor='admin'))
        before=(t.Movement.query.count(),accrual.Entry.query.count(),db.session.get(t.Account,data[0]['id']).balance)
    obj=publish(client,screen)
    body={'template':obj['key'],'version':1,'options':{'organization_code':code},'filters':{'date_from':'2026-10-01','date_to':'2026-10-31'}}
    response=post(client,'/emission/'+screen,body)
    assert response.status_code==200,response.data.decode()[:2000]
    html=response.data.decode();assert '-100.01' in html and 'DRE gerencial parcial' in html
    with app.app_context():assert before==(t.Movement.query.count(),accrual.Entry.query.count(),db.session.get(t.Account,data[0]['id']).balance)
    monkeypatch.setattr(User,'has_permission',lambda self,key:key!='financial_results.list')
    assert client.get('/api/reports/emission/'+screen).status_code==403
