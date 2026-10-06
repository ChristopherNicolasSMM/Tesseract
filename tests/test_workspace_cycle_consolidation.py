"""Pacote único: planejamento, manutenção e continuidade Brewfather sem estoque."""
import pytest
from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile
from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.services import workspace_recipe_preparation as prep
from addons.addon_brewstation.features.feature_mash_control.services import workspace_plant_maintenance as maintenance
from addons.addon_brewstation.features.feature_brew_father.services import sync_service, brewfather_client
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_estoque.root.model.movimentacao import Movimentacao


@pytest.fixture
def app(): return create_app(env="testing")


@pytest.fixture
def client(app): return app.test_client()


def setup(app):
    with app.app_context():
        plant = BrewPlant(name="Planta consolidada")
        recipe = MashRecipe(name="Receita consolidada", origem_receita="Manual", versao=1)
        db.session.add_all([plant, recipe])
        db.session.commit()
        return plant.id, recipe.id


def login(app, client):
    with app.app_context():
        user = User(username="cycle", email="cycle@test.local", nome="Cycle", nome_completo="Cycle", celular="0", is_admin=True, is_active=True)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
    client.post('/api/auth/login', json={"username":"cycle", "password":"password"})


DATA = {"recipe": {"name":"Receita editada", "description":"Descrição local", "volume_planejado_litros":"20,5"},
        "fermentation": {"nome":"Fermentação", "temperatura":"18", "tempo_dias":"7", "ordem":"0"},
        "water": {"contexto":"source", "calcio":"50", "ph":"7"}}


def test_preparation_historico_atomicidade_e_lixeira_sem_estoque(app):
    _, rid = setup(app)
    with app.app_context():
        before = Movimentacao.query.count()
        prep.save_preparation(rid, 'recipe', 'save', DATA['recipe'])
        assert db.session.get(MashRecipe, rid).volume_planejado_litros == 20.5
        for kind, model in [('fermentation', FermentationStep), ('water', WaterProfile)]:
            row = prep.save_preparation(rid, kind, 'save', DATA[kind])
            count = RecipeHistory.query.count()
            assert prep.save_preparation(rid, kind, 'save', DATA[kind], row_id=row['id']) == row
            assert RecipeHistory.query.count() == count
            prep.save_preparation(rid, kind, 'trash', {}, row_id=row['id'])
            timestamp = db.session.get(model, row['id']).deleted_at
            prep.save_preparation(rid, kind, 'trash', {}, row_id=row['id'])
            assert db.session.get(model, row['id']).deleted_at == timestamp
            prep.save_preparation(rid, kind, 'restore', {}, row_id=row['id'])
            assert not db.session.get(model, row['id']).is_deleted
        assert RecipeHistory.query.count() == 7
        assert RecipeHistory.query.order_by(RecipeHistory.id.desc()).first().get_snapshot()['preparation_action']['action'] == 'restore'
        assert Movimentacao.query.count() == before


@pytest.mark.parametrize('deleted', [False, True])
@pytest.mark.parametrize('kind', ['recipe', 'fermentation', 'water'])
def test_preparation_receita_usada_nunca_muda_mesmo_com_lote_na_lixeira(app, kind, deleted):
    pid, rid = setup(app)
    with app.app_context():
        row = prep.save_preparation(rid, kind, 'save', DATA[kind])
        db.session.add(BrewSession(name="Histórico", plant_id=pid, recipe_id=rid, status='completed', is_deleted=deleted))
        db.session.commit()
        before = RecipeHistory.query.count()
        for action in ['save', 'trash', 'restore']:
            with pytest.raises(prep.PreparationConflict):
                prep.save_preparation(rid, kind, action, DATA[kind] if action == 'save' else {}, row_id=None if kind == 'recipe' else row['id'])
        assert RecipeHistory.query.count() == before


@pytest.mark.parametrize('kind,field,value', [('recipe','volume_planejado_litros','nan'),('recipe','volume_planejado_litros',-1),
    ('recipe','name',''),('recipe','name','x'*101),('fermentation','temperatura',-6),('fermentation','tempo_dias',-1),
    ('fermentation','ordem',1.5),('fermentation','ordem',2147483648),('water','ph',15),('water','calcio','inf'),('water','contexto','inexistente')])
def test_preparation_rejeita_dados_invalidos(app, kind, field, value):
    _, rid = setup(app)
    with app.app_context():
        data = {**DATA[kind], field:value}
        with pytest.raises(ValueError): prep.save_preparation(rid, kind, 'save', data)
        assert RecipeHistory.query.count() == 0
        assert FermentationStep.query.count() == WaterProfile.query.count() == 0


def test_preparation_contexto_unico_inclui_lixeira_e_nao_permite_troca(app):
    _, rid = setup(app)
    with app.app_context():
        row = prep.save_preparation(rid, 'water', 'save', DATA['water'])
        with pytest.raises(prep.PreparationConflict): prep.save_preparation(rid, 'water', 'save', {**DATA['water'], 'contexto':'mash'}, row_id=row['id'])
        prep.save_preparation(rid, 'water', 'trash', {}, row_id=row['id'])
        with pytest.raises(prep.PreparationConflict): prep.save_preparation(rid, 'water', 'save', DATA['water'])
        assert WaterProfile.query.count() == 1


@pytest.mark.parametrize('kind', ['recipe', 'fermentation', 'water'])
def test_preparation_rollback_se_snapshot_nao_persistir(app, monkeypatch, kind):
    _, rid = setup(app)
    with app.app_context():
        name = db.session.get(MashRecipe, rid).name
        def fail():
            db.session.flush()
            raise RuntimeError('falha no commit')
        monkeypatch.setattr(db.session, 'commit', fail)
        with pytest.raises(RuntimeError): prep.save_preparation(rid, kind, 'save', DATA[kind])
        assert RecipeHistory.query.count() == 0
        assert FermentationStep.query.count() == WaterProfile.query.count() == 0
        assert db.session.get(MashRecipe, rid).name == name


def test_preparation_pertencimento_e_conflito_de_nome(app):
    _, rid = setup(app)
    with app.app_context():
        other = MashRecipe(name='Outra receita', versao=1, origem_receita='Manual')
        db.session.add(other); db.session.commit()
        row = prep.save_preparation(rid, 'water', 'save', DATA['water'])
        with pytest.raises(prep.PreparationNotFound): prep.save_preparation(other.id, 'water', 'save', DATA['water'], row_id=row['id'])
        with pytest.raises(prep.PreparationConflict): prep.save_preparation(rid, 'recipe', 'save', {**DATA['recipe'], 'name':'Outra receita'})


def test_workspace_preparation_http_forms_snapshot_e_retorno(app, client):
    pid, rid = setup(app); login(app, client)
    for kind in DATA:
        response = client.post(f'/brewstation/plant-workspace/{pid}/recipes/{rid}/preparation/{kind}/save', data=DATA[kind], headers={'X-Requested-With':'XMLHttpRequest'})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['recipe_id'] == rid
    html = client.get(f'/brewstation/plant-workspace/{pid}/tab/recipe?recipe_id={rid}').data.decode()
    assert 'Dados gerais planejados' in html and 'Descrição local' in html
    assert 'name="contexto" class="form-select"' in html
    assert 'brewstation_mashctrl.preparation.general' not in html
    assert 'pw-process-mutation' in html


@pytest.mark.parametrize('kind,code', [('recipe','mash_recipes.update'),('water','water_profiles.create'),('fermentation','fermentation_steps.create')])
def test_workspace_preparation_permissao(app, client, monkeypatch, kind, code):
    pid, rid = setup(app); login(app, client)
    monkeypatch.setattr(User, 'has_permission', lambda self, permission: permission != code)
    response = client.post(f'/brewstation/plant-workspace/{pid}/recipes/{rid}/preparation/{kind}/save', data=DATA[kind], headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code == 403


def configuration(app):
    pid, rid = setup(app)
    with app.app_context():
        vessel = BrewPlantVessel(plant_id=pid, label_text='Tanque consolidado', vessel_type='mash_tun')
        function = DeviceFunction(name='cycle_temp', display_name='Temperatura', category='sensor')
        db.session.add_all([vessel,function]); db.session.commit()
        return pid, rid, vessel.id


def test_maintenance_lixeira_restaura_sem_cascata_e_idempotente(app):
    pid, _, vid = configuration(app)
    with app.app_context():
        mapping = BrewPlantMapping(vessel_id=vid, role_key='sensor_temp', device_function_name='cycle_temp')
        db.session.add(mapping); db.session.commit(); mid=mapping.id
        with pytest.raises(maintenance.MaintenanceConflict): maintenance.maintain(pid,'vessels',vid,'trash')
        maintenance.maintain(pid,'mappings',mid,'trash')
        stamp=mapping.deleted_at
        maintenance.maintain(pid,'mappings',mid,'trash')
        assert mapping.deleted_at == stamp
        maintenance.maintain(pid,'vessels',vid,'trash')
        with pytest.raises(maintenance.MaintenanceConflict): maintenance.maintain(pid,'mappings',mid,'restore')
        maintenance.maintain(pid,'vessels',vid,'restore')
        maintenance.maintain(pid,'mappings',mid,'restore')
        maintenance.maintain(pid,'mappings',mid,'restore')
        assert not mapping.is_deleted
        assert Movimentacao.query.count() == 0


@pytest.mark.parametrize('reference', ['session','step','widget','connection','rule'])
def test_maintenance_bloqueia_referencias_sem_altera_lote_ou_atuador(app, reference):
    pid, rid, vid = configuration(app)
    with app.app_context():
        mapping = BrewPlantMapping(vessel_id=vid, role_key='sensor_temp', device_function_name='cycle_temp')
        db.session.add(mapping); db.session.commit()
        kind, record = 'vessels', vid
        if reference == 'session': db.session.add(BrewSession(name='Em andamento',plant_id=pid,recipe_id=rid,status='paused'))
        if reference == 'step':
            lot=BrewSession(name='Histórico',plant_id=pid,recipe_id=rid,status='completed');db.session.add(lot);db.session.flush()
            db.session.add(BrewSessionStep(session_id=lot.id,vessel_id=vid,name='Passo',step_index=0, status='completed'))
        if reference == 'widget':
            layout=DashboardLayout(name='Layout referenciado',plant_id=pid);db.session.add(layout);db.session.flush()
            db.session.add(DashboardWidget(layout_id=layout.id,vessel_id=vid,widget_type='vessel'))
        if reference == 'connection': db.session.get(BrewPlant,pid).plant_schema_json={'connections':[{'from_vessel_id':vid,'to_vessel_id':999}]}
        if reference == 'rule':
            db.session.add(AutomationRule(name='Ativa',sensor_function_name='cycle_temp',actor_function_name='other',condition_operator='>',condition_value=1,actor_action='ON',is_active=True))
            kind,record='mappings',mapping.id
        if kind == 'vessels': mapping.is_deleted=True
        db.session.commit()
        with pytest.raises(maintenance.MaintenanceConflict): maintenance.maintain(pid,kind,record,'trash')
        assert not (db.session.get(BrewPlantVessel,vid) if kind=='vessels' else mapping).is_deleted


def test_maintenance_restauracao_rejeita_duplicata_e_funcao_incompativel(app):
    pid,_,vid=configuration(app)
    with app.app_context():
        old=BrewPlantMapping(vessel_id=vid,role_key='sensor_temp',device_function_name='cycle_temp',is_deleted=True)
        other=BrewPlantMapping(vessel_id=vid,role_key='sensor_temp',device_function_name='cycle_temp')
        db.session.add_all([old,other]);db.session.commit()
        with pytest.raises(maintenance.MaintenanceConflict): maintenance.maintain(pid,'mappings',old.id,'restore')
        other.is_deleted=True
        DeviceFunction.query.filter_by(name='cycle_temp').one().category='actuator'
        db.session.commit()
        with pytest.raises(maintenance.MaintenanceConflict): maintenance.maintain(pid,'mappings',old.id,'restore')
        assert old.is_deleted


def test_maintenance_rollback_restauracao_e_paginacao_http(app, client, monkeypatch):
    pid,_,vid=configuration(app);login(app,client)
    with app.app_context():
        maintenance.maintain(pid,'vessels',vid,'trash')
        for i in range(21): db.session.add(BrewPlantVessel(plant_id=pid,label_text=f'Trash {i}',vessel_type='mash_tun',is_deleted=True))
        db.session.commit()
        commit=db.session.commit
        def fail(): db.session.flush();raise RuntimeError('falha')
        monkeypatch.setattr(db.session,'commit',fail)
        with pytest.raises(RuntimeError): maintenance.maintain(pid,'vessels',vid,'restore')
        assert db.session.get(BrewPlantVessel,vid).is_deleted
        monkeypatch.setattr(db.session,'commit',commit)
    html=client.get(f'/brewstation/plant-workspace/{pid}/tab/plant').data.decode()
    assert 'vessels_trash_page=2' in html
    assert 'Tanques na lixeira (22)' in html
    response=client.post(f'/brewstation/plant-workspace/{pid}/maintenance/vessels/{vid}/restore',headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==200


@pytest.mark.parametrize('code', ['brew_plants.list','brew_plant_vessels.trash'])
def test_maintenance_permissao_e_pertencimento(app, client, monkeypatch, code):
    pid,_,vid=configuration(app);login(app,client)
    with app.app_context():
        other=BrewPlant(name='Outra planta');db.session.add(other);db.session.commit();other_id=other.id
    response=client.post(f'/brewstation/plant-workspace/{other_id}/maintenance/vessels/{vid}/trash',headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==404
    monkeypatch.setattr(User,'has_permission',lambda self,permission:permission!=code)
    response=client.post(f'/brewstation/plant-workspace/{pid}/maintenance/vessels/{vid}/trash',headers={'X-Requested-With':'XMLHttpRequest'})
    assert response.status_code==403


def remote_recipe():
    return {'id':'cycle-bf', 'name':'Receita remota', 'ingredients':[
        {'name':'Whirlfloc','tipo_ingrediente':'adjunto','uso_detalhado':'Boil','amount':2,'unit':'items','use':'fervura'}],
        'fermentation_steps':[{'nome':'Remota','temperatura':18,'tempo_dias':7,'ordem':0}],
        'water_profiles':[{'contexto':'source','calcio':10}]}


@pytest.mark.parametrize('decision', ['ignorado','ambiguo'])
def test_resync_preserva_planejamento_local_e_decisoes_sem_movimentar(app, decision):
    with app.app_context():
        old=sync_service._importar_receita(remote_recipe())
        old.description='Notas locais';old.volume_planejado_litros=25
        ingredient=RecipeIngredient.query.filter_by(recipe_id=old.id).one()
        ingredient.quantidade=99;ingredient.status_resolucao='ignorado'
        if decision=='ambiguo':
            db.session.add(RecipeIngredient(recipe_id=old.id,descricao_origem='Whirlfloc',tipo_ingrediente='adjunto',uso_detalhado='Boil',status_resolucao='ignorado'))
        FermentationStep.query.filter_by(recipe_id=old.id).one().temperatura=22
        WaterProfile.query.filter_by(recipe_id=old.id).one().calcio=123
        db.session.commit();old_id=old.id
        new=sync_service._importar_receita(remote_recipe(),ressincronizar=True)
        assert new.id!=old_id and not old.is_deleted
        assert ingredient.quantidade==99
        assert new.description=='Notas locais' and new.volume_planejado_litros==25
        new_item=RecipeIngredient.query.filter_by(recipe_id=new.id).one()
        assert new_item.quantidade==2
        assert new_item.status_resolucao==('ignorado' if decision=='ignorado' else 'pendente_depara')
        assert FermentationStep.query.filter_by(recipe_id=old_id).one().temperatura==22
        assert FermentationStep.query.filter_by(recipe_id=new.id).one().temperatura==18
        assert WaterProfile.query.filter_by(recipe_id=old_id).one().calcio==123
        assert WaterProfile.query.filter_by(recipe_id=new.id).one().calcio==10
        assert RecipeHistory.query.filter_by(recipe_id=new.id).one().get_snapshot()['brewfather_import']['source_recipe_id']==old_id
        assert Movimentacao.query.count()==0


def test_resync_rollback_e_nome_remoto_alterado(app,monkeypatch):
    with app.app_context():
        old=sync_service._importar_receita(remote_recipe());old.versao=10;db.session.commit()
        changed={**remote_recipe(),'name':'Nome remoto novo'}
        new=sync_service._importar_receita(changed,ressincronizar=True)
        assert new.versao>old.versao
        assert sync_service._importar_receita(changed).id==new.id
        count=MashRecipe.query.count();hist=RecipeHistory.query.count()
        def fail(): db.session.flush();raise RuntimeError('falha snapshot')
        monkeypatch.setattr(db.session,'commit',fail)
        with pytest.raises(RuntimeError):sync_service._importar_receita(changed,ressincronizar=True)
        assert MashRecipe.query.count()==count and RecipeHistory.query.count()==hist
        assert not old.is_deleted


@pytest.mark.parametrize('context,expected',[('abc',400),('0',400),('999999',404)])
def test_portal_rejeita_contexto_antes_da_api(app,client,monkeypatch,context,expected):
    login(app,client)
    def fail(*args,**kwargs):pytest.fail('API não deve ser chamada')
    monkeypatch.setattr(brewfather_client,'get_recipe_normalizado',fail)
    response=client.post('/brewstation/brewfather-syncs/disponiveis/sincronizar',data={'workspace_plant_id':context,'origem_ids':'cycle-bf'})
    assert response.status_code==expected


def test_portal_importa_e_retorna_para_receita_na_mesma_planta(app,client,monkeypatch):
    pid,_=setup(app);login(app,client)
    monkeypatch.setattr(brewfather_client,'get_recipe_normalizado',lambda remote_id:remote_recipe())
    response=client.post('/brewstation/brewfather-syncs/disponiveis/sincronizar',data={'workspace_plant_id':pid,'origem_ids':'cycle-bf','return_url':'https://invalid.local/'})
    assert response.status_code==302
    assert f'/plant-workspace/{pid}?' in response.location and 'tab=recipe' in response.location and 'recipe_id=' in response.location
    response=client.post('/brewstation/brewfather-syncs/disponiveis/sincronizar',data={'workspace_plant_id':pid})
    assert response.status_code==302 and f'workspace_plant_id={pid}' in response.location


def test_resync_reaproveita_vinculo_local_sem_alterar_conversao(app):
    from addons.addon_estoque.root.model.material import Material
    from addons.addon_estoque.root.model.categoria import Categoria
    from addons.addon_estoque.root.model.origem import Origem
    from addons.addon_estoque.root.model.tipo_produto import TipoProduto
    from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
    from addons.addon_brewstation.features.feature_mash_control.model.ingredient_mapping import IngredientMapping
    with app.app_context():
        origin=Origem.query.first();kind=TipoProduto.query.first()
        category=Categoria(descricao='Teste ciclo',codigo='CICLO',tipo_produto_id=kind.id)
        db.session.add(category);db.session.flush()
        local=Material(nome='Whirlfloc local',sku='CYCLE-LOCAL',origem_id=origin.id,tipo_produto_id=kind.id,categoria_id=category.id,ativo=True)
        shared=Material(nome='Whirlfloc compartilhado',sku='CYCLE-SHARED',origem_id=origin.id,tipo_produto_id=kind.id,categoria_id=category.id,ativo=True)
        db.session.add_all([local,shared]);db.session.flush()
        db.session.add_all([MaterialUnidade(material_id=local.id,unidade='UN',fator_para_base=1,is_unidade_base=True),MaterialUnidade(material_id=local.id,unidade='ITEM',fator_para_base=1,is_unidade_base=False)])
        db.session.commit()
        old=sync_service._importar_receita(remote_recipe())
        item=RecipeIngredient.query.filter_by(recipe_id=old.id).one()
        item.material_id=local.id;item.status_resolucao='resolvido'
        db.session.add(IngredientMapping(origem_receita='BrewFather',descricao_origem='Whirlfloc',material_id=shared.id))
        db.session.commit()
        new=sync_service._importar_receita(remote_recipe(),ressincronizar=True)
        assert RecipeIngredient.query.filter_by(recipe_id=new.id).one().material_id==local.id
        assert MaterialUnidade.query.filter_by(material_id=local.id).count()==2
        assert MaterialUnidade.query.filter_by(material_id=local.id,unidade='ITEM').one().fator_para_base==1
        assert IngredientMapping.query.filter_by(descricao_origem='Whirlfloc').one().material_id==shared.id
        assert Movimentacao.query.count()==0
        local.ativo=False;db.session.commit()
        newest=sync_service._importar_receita(remote_recipe(),ressincronizar=True)
        result=RecipeIngredient.query.filter_by(recipe_id=newest.id).one()
        assert result.material_id is None and result.status_resolucao=='pendente_depara'


def test_maintenance_tubulacao_bloqueia_mapeamento(app):
    pid,_,vid=configuration(app)
    with app.app_context():
        row=BrewPlantMapping(vessel_id=vid,role_key='sensor_temp',device_function_name='cycle_temp')
        db.session.add(row)
        db.session.get(BrewPlant,pid).plant_schema_json={'connections':[{'flow_function_name':'cycle_temp'}]}
        db.session.commit()
        for action in ['trash','restore']:
            if action=='restore':row.is_deleted=True;db.session.commit()
            with pytest.raises(maintenance.MaintenanceConflict):maintenance.maintain(pid,'mappings',row.id,action)


@pytest.mark.parametrize('area',['','/lotes','/inventario/hops'])
def test_portal_navegacao_e_filtros_conservam_planta(app,client,monkeypatch,area):
    pid,_=setup(app);login(app,client)
    monkeypatch.setattr(brewfather_client,'list_recipes_portal_cached',lambda **kwargs:([{'_id':'cycle-bf','name':'Receita remota'}],False))
    monkeypatch.setattr(brewfather_client,'list_portal_cached',lambda *args,**kwargs:([],False))
    with app.app_context():sync_service._importar_receita(remote_recipe())
    response=client.get(f'/brewstation/brewfather-syncs/portal{area}?workspace_plant_id={pid}&q=')
    assert response.status_code==200
    html=response.data.decode()
    assert f'name="workspace_plant_id" value="{pid}"' in html
    assert f'workspace_plant_id={pid}' in html
    assert f'/plant-workspace/{pid}?tab=recipe' in html


def test_portal_contexto_exige_permissao_antes_de_importar(app,client,monkeypatch):
    pid,_=setup(app);login(app,client)
    monkeypatch.setattr(User,'has_permission',lambda self,permission:permission!='brew_plants.list')
    monkeypatch.setattr(brewfather_client,'get_recipe_normalizado',lambda *args:pytest.fail('API não deve ser chamada'))
    response=client.post('/brewstation/brewfather-syncs/disponiveis/sincronizar',data={'workspace_plant_id':pid,'origem_ids':'cycle-bf'})
    assert response.status_code==403
