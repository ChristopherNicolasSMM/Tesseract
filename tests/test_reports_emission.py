"""Emissão contextual, filtros reais, contratos e segregação organizacional."""
import uuid
from decimal import Decimal
import pytest
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction
from addons.addon_reports.root.services import report_emission_service as emission
from addons.addon_reports.root.services import report_library_service as library
from addons.addon_reports.root.services.report_layout_service import validate_data
from tests.test_reports_workspace import app,client,create,read,save,post


def publish(client,name):
    obj=create(client);value=read(client,obj['id']);value.update(library.definition(name))
    assert save(client,obj['id'],value).status_code==200
    assert post(client,f"/templates/{obj['id']}/versions/1/publish",{'lock_version':2}).status_code==200
    return obj


@pytest.mark.parametrize('screen',list(emission.SCREENS))
def test_screens_render_filters_and_metadata(client,screen):
    owner=emission.SCREENS[screen][3]
    response=client.get('/'+owner+'/reports/'+screen)
    assert response.status_code==200
    html=response.data.decode();assert 'reports_emission.js' in html and 'emission-template' in html
    assert 'sandbox="allow-same-origin allow-modals"' in html
    assert client.get('/api/reports/emission/'+screen).status_code==200


def test_menu_nested_groups_and_routes(app,client):
    with app.app_context():
        for owner,parent in [('brewstation','TX_GROUP_BREWSTATION'),('estoque','TX_GROUP_ESTOQUE')]:
            group=Transaction.query.filter_by(code='TX_GROUP_REPORTS_'+owner.upper()).one()
            assert group.parent.code==parent and group.route is None
            for name,config in emission.SCREENS.items():
                if config[3]!=owner:continue
                entry=Transaction.query.filter_by(code='TX_REPORT_EMIT_'+name.upper().replace('-','_')).one()
                assert entry.parent_id==group.id and entry.route=='/'+owner+'/reports/'+name
    assert client.get('/brewstation/reports/estoque').status_code==404


def test_recipe_emission_published_contract_and_csrf(client,app):
    from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
    with app.app_context():
        row=MashRecipe(name='Receita contextual REAL');db.session.add(row);db.session.commit();ident=row.id;before=row.to_dict()
    obj=publish(client,'receita-completa');wrong=publish(client,'banco-leveduras')
    body={'template':obj['key'],'version':1,'options':{'recipe_id':ident},'filters':{}}
    assert client.post('/api/reports/emission/receitas',json=body).status_code==403
    response=post(client,'/emission/receitas',body);assert response.status_code==200
    assert 'Receita contextual REAL' in response.data.decode()
    assert post(client,'/emission/receitas',{**body,'template':wrong['key']}).status_code==404
    assert post(client,'/emission/receitas',{**body,'filters':{'unknown':True}}).status_code==422
    assert post(client,'/emission/receitas',{**body,'options':{'recipe_id':True}}).status_code==422
    with app.app_context():assert db.session.get(MashRecipe,ident).to_dict()==before


def test_organization_export_segregates_and_preserves_balances(client,app):
    from services.core.organization_service import save_organization
    from addons.addon_estoque.root.model.material import Material
    from addons.addon_estoque.root.model.organization_stock import OrganizationBalance
    code=('R'+uuid.uuid4().hex[:12]).upper();other=('S'+uuid.uuid4().hex[:12]).upper()
    with app.app_context():
        assert save_organization({'code':code,'name':'Empresa do relatório'}).success
        assert save_organization({'code':other,'name':'Outra empresa'}).success
        from addons.addon_estoque.root.model.origem import Origem
        from addons.addon_estoque.root.model.tipo_produto import TipoProduto
        from addons.addon_estoque.root.model.categoria import Categoria
        category=Categoria(descricao='Categoria de relatório',codigo='RC'+uuid.uuid4().hex[:10]);db.session.add(category);db.session.flush()
        material=Material(origem_id=Origem.query.first().id,tipo_produto_id=TipoProduto.query.first().id,categoria_id=category.id,nome='Material REAL',sku='RP'+uuid.uuid4().hex[:12],unidade_medida='kg')
        db.session.add(material);db.session.flush()
        balance=OrganizationBalance(organization_code=code,material_id=material.id,currency_code='BRL',quantity=Decimal('3.5'),stock_value=Decimal('21'))
        second=OrganizationBalance(organization_code=other,material_id=material.id,currency_code='BRL',quantity=Decimal('99'),stock_value=Decimal('999'))
        db.session.add_all([balance,second]);db.session.commit();before=balance.to_dict();ident=material.id;balance_id=balance.id
    value=post(client,'/examples/estoque-organizacional/data',{'options':{'organization_code':code}}).json['item']
    validate_data(library.definition('estoque-organizacional')['data_schema'],value)
    assert len(value['items'])==1 and value['items'][0]['quantidade_atual']=='3.5'
    assert value['items'][0]['unidade']=='kg' and value['items'][0]['currency_code']=='BRL'
    obj=publish(client,'estoque-organizacional')
    body={'template':obj['key'],'version':1,'options':{'organization_code':code},'filters':{'positive_only':True}}
    response=post(client,'/emission/estoque',body);assert response.status_code==200
    assert 'Empresa do relatório' in response.data.decode() and 'Material REAL' in response.data.decode()
    assert post(client,'/emission/estoque',{**body,'options':{}}).status_code==400
    assert post(client,'/emission/estoque',{**body,'filters':{'positive_only':1}}).status_code==422
    assert post(client,'/emission/estoque',{**body,'options':{'organization_code':code,'material_id':ident+100000}}).status_code==200
    with app.app_context():assert db.session.get(OrganizationBalance,balance_id).to_dict()==before


def test_filters_project_existing_rows_and_reject_inverted_dates(client,monkeypatch,app):
    with app.test_request_context():
        monkeypatch.setattr(emission,'authorize',lambda name:emission.SCREENS[name])
        monkeypatch.setattr(library,'data',lambda name,options,**kwargs:{'items':[{'id':1,'status':'active','strain_id':10,'location':'A'},{'id':2,'status':'inactive','strain_id':20,'location':'B'}]})
        assert emission.filtered_data('banco-leveduras',{}, {'status':'active','strain_id':10})['items']==[{'id':1,'status':'active','strain_id':10,'location':'A'}]
        from addons.addon_reports.root.services.report_layout_service import ReportError
        with pytest.raises(ReportError):emission.filtered_data('starters',{}, {'date_from':'2026-02-02','date_to':'2026-01-01'})


def test_emission_domain_permissions_and_feature_disabled(client,app,monkeypatch):
    monkeypatch.setattr(User,'has_permission',lambda self,key:key.startswith('report_templates.'))
    assert client.get('/brewstation/reports/receitas').status_code==403
    assert client.get('/api/reports/emission/receitas').status_code==403
    monkeypatch.undo()
    feature=app.module_manager._registered_features.pop('brewstation/feature_mash_control')
    try:assert client.get('/api/reports/emission/sessoes').status_code==503
    finally:app.module_manager._registered_features['brewstation/feature_mash_control']=feature


def test_emission_does_not_require_template_editor_access(client,monkeypatch):
    monkeypatch.setattr(User,'has_permission',lambda self,key:key!='report_templates.detail')
    assert client.get('/api/reports/emission/receitas').status_code==200
    assert client.get('/api/reports/examples/receita-completa/choices').status_code==403
