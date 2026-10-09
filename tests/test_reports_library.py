"""Biblioteca operacional, projeções reais e ausência de mutações de domínio."""
import json
from datetime import date
from pathlib import Path
import pytest
from core.db import db
from model.core.user import User
from addons.addon_reports.root.services.report_library_service import CATALOG
from addons.addon_reports.root.services.report_layout_service import ReportLayoutService, validate_data
from tests.test_reports_workspace import app, client, create, read, save, post


@pytest.mark.parametrize('name',list(CATALOG))
def test_ready_templates_are_valid_empty_and_use_real_contracts(client,name):
    response=client.get('/api/reports/examples/'+name);assert response.status_code==200
    value=response.json['item'];validate_data(value['data_schema'],value['sample_data'])
    html=ReportLayoutService.render(value['layout'],value['sample_data'],{})
    assert '<table' in html and value['layout']['page']['number_pages'] is True
    assert value['parameters']==[]
    assert value['sample_data'].get('generated_at') is None
    if name=='estoque-atual':assert 'legado' in html and 'R$' not in html
    if name=='checklist-receita':assert '[ ]' in html


def test_recipe_sources_filter_children_and_do_not_change_objects(client,app):
    from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
    from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
    with app.app_context():
        recipe=MashRecipe(name='Receita REAL',description='Dado <real>',volume_planejado_litros=25)
        other=MashRecipe(name='Outra');db.session.add_all([recipe,other]);db.session.flush()
        db.session.add_all([RecipeIngredient(recipe_id=recipe.id,descricao_origem='Malte REAL',quantidade=4.5,unidade_medida='kg'),
            RecipeIngredient(recipe_id=other.id,descricao_origem='Não exportar',quantidade=1,unidade_medida='kg'),
            RecipeStep(recipe_id=recipe.id,nome='Etapa REAL',step_type='mash',ordem=1,temperatura=65,tempo_min=40)])
        db.session.commit();ident=recipe.id;before=recipe.to_dict()
    choices=client.get('/api/reports/examples/receita-completa/choices')
    assert choices.status_code==200 and any(i['value']=={'recipe_id':ident} for i in choices.json['items'])
    for name in ('receita-completa','checklist-receita'):
        response=post(client,'/examples/'+name+'/data',{'options':{'recipe_id':ident}})
        assert response.status_code==200;data=response.json['item']
        assert [i['descricao_origem'] for i in data['ingredients']]==['Malte REAL']
        template=client.get('/api/reports/examples/'+name).json['item'];validate_data(template['data_schema'],data)
        html=ReportLayoutService.render(template['layout'],data,{})
        assert 'Malte REAL' in html and 'Não exportar' not in html
        if name=='receita-completa':assert 'Dado &lt;real&gt;' in html
    with app.app_context():assert db.session.get(MashRecipe,ident).to_dict()==before


def test_yeast_expiry_starters_and_dashboard_read_existing_records(client,app):
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_container import YeastContainer
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_device import YeastStorageDevice
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent
    with app.app_context():
        device=YeastStorageDevice(name='Dispositivo REAL');db.session.add(device);db.session.flush()
        strain=YeastStrain(code='LIB-REAL',name='Cepa REAL');container=YeastContainer(name='Caixa REAL',device_id=device.id)
        db.session.add_all([strain,container]);db.session.flush()
        values=[]
        for status,expiry in [('active',date(2026,10,10)),('active',date(2026,10,1)),('active',None),('active',date(2026,12,1)),('contaminated',date(2026,10,10))]:
            item=YeastBankItem(strain_id=strain.id,container_id=container.id,storage_type='Agar Inclinado',status=status,expiry_date=expiry,estimated_viability_pct=75)
            db.session.add(item);db.session.flush();values.append(item)
        db.session.add_all([YeastBankEvent(bank_item_id=values[0].id,event_type='Starter',starter_status='planned',start_date=date(2026,10,10),target_volume_l=1.5),
            YeastBankEvent(bank_item_id=values[0].id,event_type='Starter',starter_status='completed',target_volume_l=2)])
        db.session.commit();ids=[v.id for v in values];before=[v.to_dict() for v in values]
    for name in ('banco-leveduras','disponibilidade-validade','planejamento-starters','dashboard-geral'):
        options={'days':30,'reference_date':'2026-10-09'} if name=='disponibilidade-validade' else {}
        response=post(client,'/examples/'+name+'/data',{'options':options});assert response.status_code==200
        data=response.json['item'];template=client.get('/api/reports/examples/'+name).json['item']
        validate_data(template['data_schema'],data);html=ReportLayoutService.render(template['layout'],data,{})
        assert 'Cepa REAL' in html
        if name=='disponibilidade-validade':
            assert ids[0] in [v['id'] for v in data['expiring']]
            assert ids[1] in [v['id'] for v in data['expired']]
            assert ids[2] in [v['id'] for v in data['undated']]
            assert ids[3] in [v['id'] for v in data['available']]
            assert ids[4] not in [v['id'] for k in ('available','expiring','expired','undated') for v in data[k]]
        if name=='planejamento-starters':assert all(v['starter_status'] in ('planned','active') for v in data['items'])
    with app.app_context():assert [db.session.get(YeastBankItem,ident).to_dict() for ident in ids]==before


@pytest.mark.parametrize('name,options',[('receita-completa',{'recipe_id':True}),('sessao-detalhada',{'session_id':1}),('disponibilidade-validade',{'days':True}),('disponibilidade-validade',{'reference_date':'invalid'}),('banco-leveduras',{'filter':'all'})])
def test_invalid_source_options(client,name,options):
    assert post(client,'/examples/'+name+'/data',{'options':options}).status_code==422


def test_source_permissions_csrf_unavailable_and_not_found(client,app,monkeypatch):
    assert client.post('/api/reports/examples/banco-leveduras/data',json={}).status_code==403
    monkeypatch.setattr(User,'has_permission',lambda self,p:p.startswith('report_templates.'))
    assert post(client,'/examples/banco-leveduras/data',{}).status_code==403
    assert client.get('/api/reports/examples/receita-completa/choices').status_code==403
    assert post(client,'/examples/not-found/data',{}).status_code==404
    assert client.get('/api/reports/examples/../../etc/passwd').status_code==404
    with app.app_context():
        feature=app.module_manager._registered_features.pop('brewstation/feature_yeast_bank')
        try:assert post(client,'/examples/banco-leveduras/data',{}).status_code==503
        finally:app.module_manager._registered_features['brewstation/feature_yeast_bank']=feature


def test_detailed_session_includes_only_own_logs_and_alarms(client,app):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
    with app.app_context():
        plant=BrewPlant(name='Planta REAL');db.session.add(plant);db.session.flush()
        session=BrewSession(name='Sessão REAL',plant_id=plant.id);other=BrewSession(name='Outra sessão',plant_id=plant.id)
        db.session.add_all([session,other]);db.session.flush()
        db.session.add_all([BrewSessionLog(session_id=session.id,message='Registro REAL'),BrewSessionLog(session_id=other.id,message='Não exportar'),BrewSessionAlarm(session_id=session.id,message='Alarme REAL')])
        db.session.commit();ids={'session_id':session.id,'plant_id':plant.id};before=session.to_dict()
    response=post(client,'/examples/sessao-detalhada/data',{'options':ids});assert response.status_code==200
    value=response.json['item'];config=client.get('/api/reports/examples/sessao-detalhada').json['item']
    validate_data(config['data_schema'],value);html=ReportLayoutService.render(config['layout'],value,{})
    assert 'Registro REAL' in html and 'Alarme REAL' in html and 'Não exportar' not in html
    with app.app_context():assert db.session.get(BrewSession,ids['session_id']).to_dict()==before
    assert post(client,'/examples/sessao-detalhada/data',{'options':{**ids,'plant_id':999999}}).status_code==404


def test_stock_template_remains_compatible_with_existing_exporter(client):
    response=post(client,'/examples/estoque-atual/data',{})
    assert response.status_code==200
    value=response.json['item'];value.pop('generated_at')
    config=client.get('/api/reports/examples/estoque-atual').json['item']
    validate_data(config['data_schema'],value)
    assert '<table' in ReportLayoutService.render(config['layout'],value,{})
