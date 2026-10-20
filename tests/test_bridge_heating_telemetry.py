"""Core side of the shared Bridge contract, MQTT adapter and advisory integration."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tests.test_dashboard_runtime import app, _criar_actor, db, device_service
from tests.test_heating_requests import env
from addons.addon_device_manager.root.services import mqtt_client_service as mqtt
from addons.addon_device_manager.root.services.bridge_heating_telemetry import validate, fresh
from addons.addon_brewstation.features.feature_mash_control.services import (
    heating_configuration_service as configuration, heating_request_service as engine,
    heating_telemetry_service as telemetry)
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.heating_request import HeatingRequest

FIXTURE=Path(__file__).parent/'fixtures/heating_telemetry_v1.json'


def frame(): return json.loads(FIXTURE.read_text())


def test_common_contract_and_separate_window_selection():
    value=frame()['heating']; now=datetime.fromisoformat(value['observed_at'])
    observed=validate(value,'mash_heater',now)
    assert observed['demand_percent']==95 and observed['selected_percent']==60 and observed['applied_window_percent']==100
    assert fresh(observed,now) and not fresh(observed,now+timedelta(seconds=16))
    assert observed['backend']=='simulated'


@pytest.mark.parametrize('key,value', [('version',True),('version',1.0),('version',2),('device_id','wrong'),
    ('sequence',True),('sequence',0),('sequence',1.5),('boot_id',''),('observed_at','2026-10-20T15:00:00'),
    ('owner','unknown'),('owner',[]),('backend','unknown'),('external_policy','automatic'),
    ('output_on',1),('demand_percent',float('nan')),('power_limit_percent',101),
    ('selected_percent',None),('applied_window_percent',-1),('temperature',float('inf')),('window_seconds',0)])
def test_reject_invalid_contract(key,value):
    data=frame()['heating'];now=datetime.fromisoformat(data['observed_at']);data[key]=value
    with pytest.raises((ValueError,TypeError)):validate(data,'mash_heater',now)


def test_replay_retained_clock_and_boot_validation():
    data=frame()['heating'];now=datetime.fromisoformat(data['observed_at']);previous=validate(data,'mash_heater',now)
    for candidate,received,retained in [(data,now,False),(data,now,True),
        ({**data,'sequence':2},now-timedelta(seconds=3),False),
        ({**data,'sequence':2},now+timedelta(seconds=121),False),
        ({**data,'boot_id':'other'},now,False)]:
        with pytest.raises(ValueError):validate(candidate,'mash_heater',received,previous,retained)
    new={**data,'boot_id':'restarted','observed_at':(now+timedelta(seconds=1)).isoformat()}
    assert validate(new,'mash_heater',now+timedelta(seconds=1),previous)['boot_id']=='restarted'


def test_mqtt_adapter_decodes_bridge_json_and_preserves_observations_on_command(app):
    with app.app_context():
        actor=_criar_actor(name='mash_heater',function_name='mash_heater',category='actuator',actor_type='actuator')
        actor.set_config({'mqtt_config':{'state_topic':'actuators/mash_heater/state'}});db.session.commit()
        identifier=actor.external_id
        data=frame();data['heating']['observed_at']=datetime.now(timezone.utc).isoformat()
        def deliver(payload,retained=False):
            msg=SimpleNamespace(topic=mqtt._full_topic('actuators/mash_heater/state'),payload=json.dumps(payload).encode(),retain=retained)
            mqtt._on_message(None,{'app':app},msg);db.session.expire_all()
        deliver(data)
        observed=device_service.get_heating_telemetry(identifier)
        assert observed['owner']=='local_recipe' and device_service.get_value(identifier) is True
        device_service.set_value(identifier,False,publish=False)
        assert device_service.get_heating_telemetry(identifier)==observed
        deliver({**data,'heating':{**data['heating'],'sequence':2}},retained=True)
        assert device_service.get_heating_telemetry(identifier)==observed
        deliver({'value':False})
        assert device_service.get_heating_telemetry(identifier) is None


def test_temperature_ingress_is_numeric_not_json_text(app):
    with app.app_context():
        actor=_criar_actor(name='actual_temp',function_name='actual_temp',unit='°C')
        actor.set_config({'mqtt_config':{'state_topic':'sensors/actual_temp/state'}});db.session.commit()
        identifier=actor.external_id
        msg=SimpleNamespace(topic=mqtt._full_topic('sensors/actual_temp/state'),payload=b'{"value": 65.5}',retain=False)
        mqtt._on_message(None,{'app':app},msg);db.session.expire_all()
        assert device_service.get_observation(identifier)['value']==65.5


@pytest.fixture
def controlled(env,monkeypatch):
    _criar_actor(name='mash_heater',function_name='mash_heater',category='actuator',actor_type='actuator')
    mapping=BrewPlantMapping(vessel_id=env.vessel.id,role_key='actor_heat',device_function_name='mash_heater')
    db.session.add(mapping);db.session.commit()
    cfg=configuration.config(env.vessel);cfg['controller_mapping_id']=mapping.id;cfg['rule']['demand_source']='bridge'
    env.vessel.heating_config_json=cfg;db.session.commit()
    env.telemetry={**frame()['heating'],'backend':'real','source':'bridge_heating_v1',
        'observed_at':env.clock.isoformat(),'received_at':env.clock.isoformat()}
    monkeypatch.setattr(device_service,'get_heating_telemetry',lambda identifier:deepcopy(env.telemetry))
    return env


def test_bridge_demand_generates_advisory_using_raw_demand_not_limited_power(controlled):
    env=controlled
    for second in (0,5,10):
        env.sample(second)
        env.telemetry.update(observed_at=env.clock.isoformat(),received_at=env.clock.isoformat())
        engine.on_observation(function_name='mash_heater')
    request=HeatingRequest.query.one()
    assert request.context_json['demand_percent']==95 and request.context_json['context'][-1]=='contract-boot'
    assert telemetry.read(env.vessel,env.clock)['selected_percent']==60


@pytest.mark.parametrize('changes',[{'backend':'simulated'},{'owner':'local_manual'},{'owner':'remote_manual'},
    {'owner':'failsafe'},{'owner':'idle'},{'target':66},{'temperature':59},{'fault':'failed'},{'demand_percent':None}])
def test_invalid_or_manual_controller_blocks_advisory(controlled,changes):
    controlled.telemetry.update(changes)
    data=engine.facts(controlled.vessel,controlled.clock)
    assert not data['valid'] and 'Bridge' in data['reason']


def test_bridge_restart_invalidates_pending_request(controlled):
    env=controlled
    for second in (0,5,10):
        env.sample(second);env.telemetry.update(observed_at=env.clock.isoformat(),received_at=env.clock.isoformat())
        engine.evaluate(env.vessel.id,env.clock)
    request=HeatingRequest.query.one()
    env.sample(11);env.telemetry.update(boot_id='restarted',observed_at=env.clock.isoformat(),received_at=env.clock.isoformat())
    engine.evaluate(env.vessel.id,env.clock)
    db.session.refresh(request)
    assert request.status=='cancelled'


def test_controller_selection_is_scoped_and_profile_upgrade_preserves_it(controlled):
    env=controlled
    env.session.status='completed';db.session.commit()
    expected=configuration.config(env.vessel)['controller_mapping_id']
    data={'usage':'hlt','target_temp':65,'expected_version':3}
    configuration.save_profile(env.vessel,data)
    assert configuration.config(env.vessel)['controller_mapping_id']==expected
    with pytest.raises(configuration.HeatingError):
        configuration.save_profile(env.vessel,{**data,'expected_version':4,'controller_mapping_id':99999})


def test_importer_populates_missing_topics_without_replacing_user_changes(app):
    from tests.test_bridge_import import DEVICES_YAML
    from addons.addon_brewstation.features.feature_mash_control.services import bridge_import_service as importer
    import yaml
    with app.app_context():
        entries=yaml.safe_load(DEVICES_YAML)['devices']
        device,_=importer._get_or_create_bridge_device('Bridge contract')
        importer._import_devices(entries,device);db.session.commit()
        from addons.addon_device_manager.root.model.device_actor import DeviceActor
        actor=DeviceActor.query.filter_by(name=entries[0]['name']).first()
        assert actor.get_config()['mqtt_config']['state_topic']==entries[0]['state_topic']
        cfg=actor.get_config();cfg['mqtt_config']['state_topic']='custom/state';actor.set_config(cfg);db.session.commit()
        importer._import_devices(entries,device);db.session.commit()
        assert actor.get_config()['mqtt_config']['state_topic']=='custom/state'


def test_sender_respects_reported_local_only_policy_without_updating_cache(app,monkeypatch):
    with app.app_context():
        actor=_criar_actor(name='local_only',function_name='local_only',category='actuator',actor_type='actuator')
        actor.set_config({'runtime':{'last_value':False,'bridge_heating':{'external_policy':'local_only'}}});db.session.commit()
        def forbidden(*args, **kwargs):pytest.fail('Rejected command was published')
        monkeypatch.setattr(device_service,'_maybe_publish',forbidden)
        assert device_service.set_value(actor.external_id,60) is False
        assert device_service.set_value(actor.external_id,None) is False
        assert device_service.get_value(actor.external_id) is False
        monkeypatch.setattr(device_service,'_maybe_publish',lambda *args:None)
        assert device_service.set_value(actor.external_id,0) is True


def test_retained_sensor_value_is_cache_only_and_cannot_look_fresh(app):
    with app.app_context():
        actor=_criar_actor(name='retained_temp',function_name='retained_temp',unit='°C')
        device_service.update_from_mqtt(actor,65,retained=True)
        assert device_service.get_value(actor.external_id)==65
        assert device_service.get_observation(actor.external_id) is None
