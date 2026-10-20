"""Leased source integration; MQTT is captured, never connected to real devices."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from tests.test_heating_requests import env
from tests.test_dashboard_runtime import app, client, _login_admin, _criar_actor, db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.services import (
    automatic_heating_service as auto, heating_configuration_service as config)
from addons.addon_device_manager.root.services import device_service, mqtt_client_service as mqtt
from addons.addon_device_manager.root.services.bridge_source_control import validate, fresh


def frame():
    return dict(version=1,device_id='gas',boot_id='boot',arm_token='token',sequence=1,
        observed_at=datetime.now(timezone.utc).isoformat(),backend='simulated',participation='primary',
        temperature_sensor='rule_temp',temperature=60,controller_device=None,
        armed=False,lease_id=None,output_on=False,target=None,reason='Desabilitado',fault=None,
        external_protection='independent_hardware',limits={})


@pytest.mark.parametrize('bad', [dict(version=True),dict(sequence=0),dict(sequence=True),dict(armed=1),
    dict(output_on=True),dict(target=float('nan')),dict(boot_id=''),dict(participation='invalid'),
    dict(external_protection='none'),dict(lease_id='unarmed'),dict(device_id='other')])
def test_rejects_invalid_source_contract(bad):
    with pytest.raises((ValueError,TypeError)):validate({**frame(),**bad},'gas',datetime.now(timezone.utc))


def test_source_replay_retained_and_freshness():
    f=frame();now=datetime.now(timezone.utc);result=validate(f,'gas',now)
    assert fresh(result,now)
    assert not fresh(result,now+timedelta(seconds=6))
    for retained,previous in ((True,None),(False,result)):
        with pytest.raises(ValueError):validate(f,'gas',now,previous,retained)


@pytest.fixture
def automatic(env,monkeypatch):
    actor=_criar_actor(name='gas',function_name='gas',category='actuator',actor_type='actuator')
    actor.set_config({'mqtt_config':{'state_topic':'gas/state','command_topic':'gas/set'}})
    mapping=BrewPlantMapping(vessel_id=env.vessel.id,role_key='aux_heat',device_function_name='gas')
    db.session.add(mapping);db.session.commit()
    source=config.config(env.vessel)['sources'][0]
    env.session.status='completed';db.session.commit()
    config.save_source(env.vessel,dict(name='Gas',type='gas',role='primary',mode='automatic',enabled=True,
        device_function_name='gas',expected_version=env.vessel.heating_version),source['id'])
    env.session.status='active';db.session.commit()
    current=validate(frame(),'gas',datetime.now(timezone.utc))
    sent=[]
    monkeypatch.setattr(device_service,'get_source_telemetry',lambda identifier:deepcopy(current))
    monkeypatch.setattr(device_service,'send_source_command',lambda identifier,value:sent.append((identifier,deepcopy(value))) or True)
    auto.leases().clear()
    return SimpleNamespace(env=env,actor=actor,source_id=source['id'],frame=current,sent=sent)


def test_arm_renew_stop_and_pause_require_new_arm(automatic):
    a=automatic;v=a.env.vessel
    auto.control(v,a.source_id,'arm',7)
    command=a.sent[-1][1]
    assert command['action']=='arm' and command['target']==65
    assert auto.view(v,auto.source_for(v,a.source_id))['output_on'] is False
    a.frame.update(armed=True,lease_id=command['lease_id'],arm_token='rotated')
    auto.on_observation('gas')
    assert a.sent[-1][1]['action']=='renew' and a.sent[-1][1]['sequence']==2
    count=len(a.sent)
    auto.on_observation('rule_temp')
    assert len(a.sent)==count # Browser and unrelated observations never renew.
    a.env.session.status='paused';db.session.commit()
    auto.reconcile_plant(v.plant_id)
    assert not auto.leases() and a.sent[-1][1]['action']=='stop'
    a.env.session.status='active';db.session.commit()
    auto.on_observation('gas')
    assert not auto.leases()


@pytest.mark.parametrize('change', ['expired','boot','target','fault','disabled','wrong_lease'])
def test_invalidation_sends_stop_without_rearming(automatic,change):
    a=automatic;v=a.env.vessel
    auto.control(v,a.source_id,'arm',7);command=a.sent[-1][1]
    a.frame.update(armed=True,lease_id=command['lease_id'],arm_token='rotated')
    if change=='expired':a.frame['received_at']=(datetime.now(timezone.utc)-timedelta(seconds=6)).isoformat()
    if change=='boot':a.frame['boot_id']='new'
    if change=='target':v.heating_config_json={**v.heating_config_json,'target_temp':66};db.session.commit()
    if change=='fault':a.frame['fault']='Sensor failed'
    if change=='disabled':a.frame.update(armed=False,lease_id=None)
    if change=='wrong_lease':a.frame['lease_id']='other'
    auto.on_observation('gas')
    assert not auto.leases() and a.sent[-1][1]['action']=='stop'


def test_network_failure_never_records_an_authorization(automatic,monkeypatch):
    a=automatic
    monkeypatch.setattr(device_service,'send_source_command',lambda *args:False)
    with pytest.raises(config.HeatingError):auto.control(a.env.vessel,a.source_id,'arm',7)
    assert not auto.leases()


def test_route_requires_login_and_scopes_source(automatic,app,client):
    a=automatic;v=a.env.vessel
    url=f'/brewstation/plant-workspace/{v.plant_id}/vessels/{v.id}/heating/sources/{a.source_id}/automatic'
    assert client.post(url,json={'action':'arm'}).status_code in (302,401)
    _login_admin(app,client)
    assert client.post(url.replace(a.source_id,'wrong'),json={'action':'arm'}).status_code==404
    assert client.post(url,json={'action':'arm'}).status_code==200
    assert client.post(url,json={'action':'stop'}).status_code==200


def test_actual_mqtt_adapter_stores_source_and_generic_on_is_blocked(app,monkeypatch):
    with app.app_context():
        a=_criar_actor(name='gas',function_name='gas',category='actuator',actor_type='actuator')
        a.set_config({'mqtt_config':{'state_topic':'gas/state','command_topic':'gas/set'}});db.session.commit()
        f=frame()
        mqtt._on_message(None,{'app':app},SimpleNamespace(topic=mqtt._full_topic('gas/state'),
            payload=json.dumps({'value':False,'heat_source':f}).encode(),retain=False))
        assert device_service.get_source_telemetry(a.external_id)['arm_token']=='token'
        assert device_service.set_value(a.external_id,True) is False
        before=device_service.get_source_telemetry(a.external_id)
        device_service.set_value(a.external_id,False,publish=False)
        assert device_service.get_source_telemetry(a.external_id)==before


def test_sensor_identity_and_auxiliary_controller_must_match(automatic,monkeypatch):
    a=automatic;v=a.env.vessel;source=auto.source_for(v,a.source_id)
    a.frame['temperature_sensor']='another_sensor'
    with pytest.raises(config.HeatingError):auto.facts(v,source)
    a.frame['temperature_sensor']='rule_temp';a.frame['temperature']=61
    with pytest.raises(config.HeatingError):auto.facts(v,source)
    a.frame.update(temperature=60,participation='auxiliary',controller_device='main_heater')
    source={**source,'role':'auxiliary'}
    from addons.addon_brewstation.features.feature_mash_control.services import heating_telemetry_service
    controller=dict(fresh=True,device_id='main_heater',backend='simulated',owner='local_recipe',target=65,fault=None)
    monkeypatch.setattr(heating_telemetry_service,'read',lambda *args,**kwargs:controller)
    assert auto.facts(v,source)[2]==65
    for key,value in [('fresh',False),('owner','remote_manual'),('target',66),('device_id','other'),('fault','failure')]:
        good=controller[key];controller[key]=value
        with pytest.raises(config.HeatingError):auto.facts(v,source)
        controller[key]=good


def test_bridge_fixture_reaches_actual_core_mqtt_adapter(app):
    from pathlib import Path
    with app.app_context():
        a=_criar_actor(name='gas',function_name='gas',category='actuator',actor_type='actuator')
        a.set_config({'mqtt_config':{'state_topic':'gas/state','command_topic':'gas/set'}});db.session.commit()
        payload=json.loads((Path(__file__).parent/'fixtures/heat_source_v1.json').read_text())
        payload['heat_source']['observed_at']=datetime.now(timezone.utc).isoformat()
        mqtt._on_message(None,{'app':app},SimpleNamespace(topic=mqtt._full_topic('gas/state'),
            payload=json.dumps(payload).encode(),retain=False))
        result=device_service.get_source_telemetry(a.external_id)
        assert result['boot_id']=='source-contract-boot' and result['temperature']==60
        assert result['external_protection']=='independent_hardware' and result['output_on'] is False


def test_stop_uses_legacy_compatible_off_without_touching_observations(app,monkeypatch):
    with app.app_context():
        a=_criar_actor(name='gas',function_name='gas',category='actuator',actor_type='actuator')
        a.set_config({'mqtt_config':{'command_topic':'gas/set'},'runtime':{'last_value':True}});db.session.commit()
        sent=[]
        monkeypatch.setattr(mqtt,'is_connected',lambda:True)
        monkeypatch.setattr(mqtt,'publish',lambda topic,payload,**options:sent.append((topic,payload,options)) or True)
        assert device_service.send_source_command(a.external_id,{'action':'stop'})
        assert sent==[('gas/set',{'value':False},{'qos':1,'retain':False})]
        assert device_service.get_value(a.external_id) is True
