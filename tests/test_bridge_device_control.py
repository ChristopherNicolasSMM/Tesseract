from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from tests.test_dashboard_runtime import app, client, _login_admin, _criar_actor, _criar_plant_vessel_mapping, db
from addons.addon_device_manager.root.services import device_service, mqtt_client_service as mqtt
from addons.addon_device_manager.root.services.bridge_device_control import validate, fresh, command
from addons.addon_brewstation.features.feature_mash_control.services import bridge_control_service as controls, heating_configuration_service as configuration


def frame():
    return {'version':1,'device_id':'heater','boot_id':'boot','sequence':1,'observed_at':datetime.now(timezone.utc).isoformat(),
        'backend':'simulated','kind':'power','external_policy':'manual_override','output_on':False,'manual_enabled':False,
        'manual_percent':40,'owner':'local_recipe','fault':None,'pending_confirmation':False,'last_command':None}


@pytest.mark.parametrize('key,value',[('version',True),('sequence',True),('sequence',0),('device_id','wrong'),('boot_id',''),
    ('kind','gas'),('output_on',1),('manual_enabled',None),('manual_percent',101),('manual_percent',float('nan')),('owner','unknown'),('backend','unknown')])
def test_reject_invalid_frame(key,value):
    data=frame();data[key]=value
    with pytest.raises((ValueError,TypeError)):validate(data,'heater',datetime.now(timezone.utc))


def test_freshness_replay_policy_and_action_validation():
    data=frame(); now=datetime.now(timezone.utc); state=validate(data,'heater',now)
    assert fresh(state,now)
    assert not fresh(state,now+timedelta(seconds=6))
    for retained,previous in [(True,None),(False,state)]:
        with pytest.raises(ValueError):validate(data,'heater',now,previous,retained)
    for action,value in [('pump_set',True),('power_prepare',True),('power_prepare',101),([],None)]:
        with pytest.raises(ValueError):command(state,action,value)
    assert command(state,'power_prepare',25)['value']==25
    state['external_policy']='local_only'
    with pytest.raises(ValueError):command(state,'power_release')
    assert command(state,'power_off')['action']=='power_off'


def test_mqtt_and_commands_do_not_optimistically_modify_observation(app,monkeypatch):
    with app.app_context():
        actor=_criar_actor(name='heater',function_name='heater',category='actuator',actor_type='actuator')
        actor.set_config({'mqtt_config':{'state_topic':'heater/state','command_topic':'heater/set'}});db.session.commit()
        payload={'value':False,'control':frame()}
        msg=SimpleNamespace(topic=mqtt._full_topic('heater/state'),payload=json.dumps(payload).encode(),retain=False)
        mqtt._on_message(None,{'app':app},msg)
        before=deepcopy(actor.get_config())
        calls=[]
        monkeypatch.setattr(mqtt,'is_connected',lambda:True)
        monkeypatch.setattr(mqtt,'publish',lambda *a,**kw:calls.append((a,kw)) or True)
        request_id=device_service.send_device_control(actor.external_id,'power_prepare',70)
        assert calls[0][0][1]['device_control']['request_id']==request_id
        assert calls[0][1]=={'qos':1,'retain':False}
        assert actor.get_config()==before
        assert device_service.set_value(actor.external_id,True) is False
        assert actor.get_config()==before
        assert device_service.get_control_telemetry(actor.external_id)['manual_percent']==40
        assert device_service.set_value(actor.external_id,False)
        assert calls[-1][0][1]=={'value':False}
        assert actor.get_config()==before


def test_widget_scope_route_and_no_actuation_on_snapshot(app,client,monkeypatch):
    _login_admin(app,client)
    with app.app_context():
        actor=_criar_actor(name='heater',function_name='heater',category='actuator',actor_type='actuator')
        plant,vessel,mapping=_criar_plant_vessel_mapping(function_name='heater',role_key='actor_heat')
        cfg=configuration.config(vessel);cfg['controller_mapping_id']=mapping.id;vessel.heating_config_json=cfg;db.session.commit()
        state=validate(frame(),'heater',datetime.now(timezone.utc))
        monkeypatch.setattr(device_service,'get_control_telemetry',lambda identifier:deepcopy(state))
        calls=[]
        monkeypatch.setattr(device_service,'send_device_control',lambda *a:calls.append(a) or 'request-1')
        view=controls.view(vessel)
        assert len(view)==1 and view[0]['label']
        assert not calls
        url=view[0]['control_url']
        assert client.post(url,json={'action':'power_enable'}).json['request_id']=='request-1'
        assert len(calls)==1
        assert client.post(url.replace(f'/mappings/{mapping.id}/',f'/mappings/{mapping.id+1000}/'),json={'action':'power_enable'}).status_code==404
        assert len(calls)==1
        assert client.post(url,json=[]).status_code==400
        from model.core.user import User
        original = User.has_permission
        monkeypatch.setattr(User, 'has_permission', lambda self, code: False if code == 'brew_sessions.update' else original(self,code))
        assert client.post(url,json={'action':'power_enable'}).status_code==403
        assert len(calls)==1
        monkeypatch.setattr(User, 'has_permission', original)
        assert client.post(url.replace(f'/plant-workspace/{plant.id}/',f'/plant-workspace/{plant.id+1000}/'),json={'action':'power_enable'}).status_code==404


def test_shared_bridge_frame():
    from pathlib import Path
    data=json.loads((Path(__file__).parent/'fixtures/device_control_v1.json').read_text())['control']
    state=validate(data,'mash_heater',datetime.fromisoformat(data['observed_at']))
    assert state['manual_percent']==40 and not state['manual_enabled'] and state['owner']=='idle'
