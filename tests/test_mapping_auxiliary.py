"""Mapping regression for manual functions, auxiliary heat and both web forms."""
import pytest
from tests.test_plant_workspace import app, client, _login_admin, db, BrewPlant, BrewPlantVessel, DeviceFunction, BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.services import heating_configuration_service as heating


@pytest.fixture
def setup(app,client):
    _login_admin(app,client)
    with app.app_context():
        plant=BrewPlant(name='Planta');db.session.add(plant);db.session.flush()
        vessel=BrewPlantVessel(plant_id=plant.id,label_text='Boil',vessel_type='boil_kettle')
        gas=DeviceFunction(name='aux_gas',display_name='Aquecimento Auxiliar Gás',category='Atuador',data_type='bool')
        heat=DeviceFunction(name='heater',display_name='Resistência',category='actuator')
        sensor=DeviceFunction(name='temp',display_name='Temperatura',category='sensor')
        db.session.add_all([vessel,gas,heat,sensor]);db.session.flush()
        db.session.add(BrewPlantMapping(vessel_id=vessel.id,role_key='actor_heat',device_function_name='heater'))
        db.session.commit()
        return plant.id,vessel.id


def test_auxiliary_does_not_replace_resistance_and_can_become_source(setup,app,client):
    pid,vid=setup;url=f'/brewstation/plant-workspace/{pid}/mappings';headers={'X-Requested-With':'XMLHttpRequest'}
    data={'vessel_id':vid,'role_key':'actor_heat_aux','device_function_name':'aux_gas'}
    response=client.post(url,data=data,headers=headers)
    assert response.status_code==201,response.data
    assert client.post(url,data=data,headers=headers).status_code==409
    with app.app_context():
        assert BrewPlantMapping.query.filter_by(vessel_id=vid,role_key='actor_heat').one().device_function_name=='heater'
        vessel=db.session.get(BrewPlantVessel,vid)
        heating.save_source(vessel,dict(name='GLP',type='gas',role='auxiliary',mode='automatic',enabled=True,
            device_function_name='aux_gas',expected_version=vessel.heating_version))
        assert heating.config(vessel)['sources'][0]['device_function_name']=='aux_gas'
        # Canonical DTO aliases let the source form offer the manually-created actuator.
        assert any(m.device_function_name=='aux_gas' for m in heating.workspace_context([vessel])['heating_mappings'][vid])


def test_role_selects_include_auxiliary_on_crud_workspace_and_editor(setup,app,client):
    pid,vid=setup
    manage=client.get('/brewstation/brew-plant-mappings/').get_data(as_text=True)
    assert '<select name="role_key"' in manage
    assert 'value="actor_heat_aux"' in manage
    fragment=client.get(f'/brewstation/plant-workspace/{pid}/tab/plant').get_data(as_text=True)
    assert 'value="actor_heat_aux"' in fragment
    assert 'Atuador de aquecimento auxiliar' in fragment
    with app.app_context():
        mapping=BrewPlantMapping(vessel_id=vid,role_key='custom_existing',device_function_name='heater')
        db.session.add(mapping);db.session.commit();mid=mapping.id
    detail=client.get(f'/brewstation/brew-plant-mappings/{mid}').get_data(as_text=True)
    assert 'value="custom_existing" selected' in detail


def test_incompatible_category_and_unselected_reference_have_clear_errors(setup,client):
    pid,vid=setup;url=f'/brewstation/plant-workspace/{pid}/mappings';headers={'X-Requested-With':'XMLHttpRequest'}
    bad=client.post(url,data={'vessel_id':vid,'role_key':'actor_heat_aux','device_function_name':'temp'},headers=headers)
    assert bad.status_code==400 and 'categoria' in bad.get_json()['error']
    missing=client.post(url,data={'vessel_id':vid,'role_key':'actor_heat_aux'},headers=headers)
    assert missing.status_code==400 and 'selecione' in missing.get_json()['error']


def test_generic_creation_respects_duplicate_and_category_checks(setup,app,client):
    pid,vid=setup;url='/brewstation/brew-plant-mappings/'
    # Discover actual create route rather than assuming the manage path accepts POST.
    with app.test_request_context():
        from flask import url_for
        url=url_for('brew_plant_mappings.create')
    data={'vessel_id':vid,'role_key':'actor_heat_aux','device_function_name':'aux_gas'}
    assert client.post(url,data=data).status_code==302
    assert client.post(url,data=data).status_code==302
    with app.app_context():
        assert BrewPlantMapping.query.filter_by(vessel_id=vid,role_key='actor_heat_aux',is_deleted=False).count()==1
