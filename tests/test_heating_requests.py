"""Advisory heating rules run on received observations, never on UI polling/commands."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_dashboard_runtime import (app, client, _login_admin, _criar_actor,
    _criar_plant_vessel_mapping, db, BrewPlantMapping, BrewSession, BrewSessionStep,
    device_service, DashboardLayout)

REAL_GET_OBSERVATION = device_service.get_observation
from addons.addon_brewstation.features.feature_mash_control.model.heating_request import HeatingRequest
from addons.addon_brewstation.features.feature_mash_control.services import (
    heating_request_service as engine, heating_configuration_service as configuration,
    dashboard_runtime_service as runtime)


@pytest.fixture
def env(app, monkeypatch):
    with app.app_context():
        sensor = _criar_actor(name='rule_temp', function_name='rule_temp', unit='°C')
        demand = _criar_actor(name='rule_demand', function_name='rule_demand', unit='%')
        plant, vessel, mapping = _criar_plant_vessel_mapping(function_name='rule_temp')
        vessel.vessel_type = 'hlt'
        dm = BrewPlantMapping(vessel_id=vessel.id, role_key='sensor_demand', device_function_name='rule_demand')
        db.session.add(dm); db.session.commit()
        configuration.save_profile(vessel, dict(usage='hlt', target_temp=65,
            planned_volume_liters=25, primary_sensor_mapping_id=mapping.id, expected_version=0))
        configuration.save_source(vessel, dict(name='GLP manual', type='gas', role='auxiliary',
            mode='advisory', enabled=True, expected_version=1))
        settings = {**engine.DEFAULTS, 'enabled':True, 'source_id':configuration.config(vessel)['sources'][0]['id'],
                    'demand_mapping_id':dm.id, 'expected_version':2}
        engine.save_rule(vessel, settings)
        session = BrewSession(name='Heating session', plant_id=plant.id, status='active')
        db.session.add(session); db.session.commit()
        base = datetime.now(timezone.utc)
        state = SimpleNamespace(plant=plant, vessel=vessel, sensor=sensor, demand=demand,
            session=session, settings=settings, clock=base, observed={}, temp_mapping=mapping, demand_mapping=dm)
        def sample(seconds=0, temp=60, percent=95):
            state.clock = base+timedelta(seconds=seconds)
            state.observed = {sensor.external_id:dict(value=temp, observed_at=state.clock.isoformat(), source='mqtt_state'),
                              demand.external_id:dict(value=percent, observed_at=state.clock.isoformat(), source='mqtt_state')}
        state.sample = sample
        sample()
        monkeypatch.setattr(device_service, 'get_observation', lambda identifier: deepcopy(state.observed.get(identifier)))
        monkeypatch.setattr(engine, 'utcnow', lambda: state.clock)
        def forbidden(*args, **kwargs):
            pytest.fail('Advisory path commanded hardware')
        monkeypatch.setattr(device_service, 'set_value', forbidden)
        yield state


def evaluate(env, second, **kwargs):
    env.sample(second, **kwargs)
    engine.evaluate(env.vessel.id, env.clock)


def trigger(env):
    evaluate(env, 0)
    evaluate(env, 5)
    evaluate(env, 10)
    return HeatingRequest.query.one()


def test_sustained_demand_hysteresis_and_audited_operator_cycle(env):
    evaluate(env, 0)
    assert HeatingRequest.query.count() == 0
    evaluate(env, 5)
    assert HeatingRequest.query.count() == 0
    evaluate(env, 10)
    request = HeatingRequest.query.one()
    engine.respond(env.vessel, request.id, 'acknowledge', 7, env.clock)
    db.session.refresh(request)
    assert request.status == 'acknowledged'
    assert request.context_json['responses'] == [{'action':'acknowledge', 'user_id':7, 'at':env.clock.isoformat()}]
    evaluate(env, 11, percent=75)  # Hysteresis band: keep the same request.
    assert request.status == 'acknowledged'
    engine.respond(env.vessel, request.id, 'complete', 9, env.clock)
    db.session.refresh(request)
    assert request.status == 'completed'
    assert [r['user_id'] for r in request.context_json['responses']] == [7,9]
    evaluate(env, 70)
    assert HeatingRequest.query.count() == 1  # No repeated requests until the condition exits.
    evaluate(env, 71, temp=64)
    evaluate(env, 72)
    evaluate(env, 77)
    evaluate(env, 82)
    assert HeatingRequest.query.count() == 2


def test_decline_response_is_compare_and_swap_and_latched(env):
    request = trigger(env)
    engine.respond(env.vessel, request.id, 'decline', 1, env.clock)
    with pytest.raises(configuration.HeatingError) as error:
        engine.respond(env.vessel, request.id, 'acknowledge', 2, env.clock)
    assert error.value.code == 409
    db.session.refresh(request)
    assert request.status == 'declined' and request.responded_by == 1
    evaluate(env, 80)
    assert HeatingRequest.query.count() == 1


@pytest.mark.parametrize('bad', [None, True, float('nan'), float('inf'), -1, 101, '95'])
def test_invalid_demand_cannot_trigger(env, bad):
    env.observed[env.demand.external_id]['value'] = bad
    engine.evaluate(env.vessel.id, env.clock)
    assert HeatingRequest.query.count() == 0
    assert 'Demanda' in env.vessel.heating_runtime_json['reason']


def test_stale_gap_and_future_readings_reset_sustained_condition(env):
    evaluate(env, 0)
    evaluate(env, 8)
    evaluate(env, 9, percent=79)  # Entry criterion not continuously satisfied.
    evaluate(env, 10)
    evaluate(env, 18)
    assert HeatingRequest.query.count() == 0
    evaluate(env, 20)
    assert HeatingRequest.query.count() == 1
    env.clock += timedelta(seconds=16)
    engine.evaluate(env.vessel.id, env.clock)
    request = HeatingRequest.query.one()
    assert request.status == 'cancelled'
    evaluate(env, 60)
    evaluate(env, 80)  # Long gap > maximum sample age resets the candidate.
    assert HeatingRequest.query.count() == 1
    env.observed[env.sensor.external_id]['observed_at'] = (env.clock+timedelta(seconds=1)).isoformat()
    engine.evaluate(env.vessel.id, env.clock)
    assert env.vessel.heating_runtime_json.get('candidate_since') is None


@pytest.mark.parametrize('change', ['pause', 'multiple_sessions', 'deleted_sensor', 'invalid_temperature', 'target', 'restart', 'expired'])
def test_revalidation_cancels_outdated_requests_before_response(env, change, app):
    request = trigger(env)
    if change == 'pause':
        env.session.status = 'paused'
    elif change == 'multiple_sessions':
        db.session.add(BrewSession(name='Ambiguous', plant_id=env.plant.id, status='active'))
    elif change == 'deleted_sensor':
        env.temp_mapping.is_deleted = True
    elif change == 'invalid_temperature':
        env.observed[env.sensor.external_id]['value'] = 111
    elif change == 'target':
        cfg = configuration.config(env.vessel); cfg['target_temp'] = 70
        env.vessel.heating_config_json = cfg
    elif change == 'restart':
        app.config['HEATING_RUNTIME_STARTED_AT'] = (env.clock+timedelta(seconds=1)).isoformat()
        env.sample(11)
    else:
        env.sample(131)
    db.session.commit()
    with pytest.raises(configuration.HeatingError) as error:
        engine.respond(env.vessel, request.id, 'acknowledge', 1, env.clock)
    assert error.value.code == 409
    db.session.refresh(request)
    assert request.status == 'cancelled'


def test_expired_request_does_not_repeat_without_exit(env):
    request = trigger(env)
    for seconds in range(20, 141, 10):
        evaluate(env, seconds)
    db.session.refresh(request)
    assert request.status == 'cancelled'
    assert HeatingRequest.query.count() == 1


def test_widget_poll_does_not_evaluate_and_historical_session_cannot_respond(env):
    for _ in range(3):
        assert engine.view(env.vessel)['requests'] == []
    assert env.vessel.heating_runtime_json is None
    request = trigger(env)
    old = BrewSession(name='Historical', plant_id=env.plant.id, status='completed')
    db.session.add(old); db.session.commit()
    assert engine.view(env.vessel, old)['requests'][0]['can_respond'] is False
    snapshot = configuration.snapshot(env.vessel, env.session)
    assert snapshot['automatic_demand_percent'] == 95
    assert snapshot['request_rule']['requests'][0]['can_respond'] is True
    assert snapshot['can_actuate'] is False


def test_process_uses_current_step_and_hlt_keeps_own_target(env):
    step = BrewSessionStep(session_id=env.session.id, vessel_id=env.vessel.id,
        name='Mash', step_index=1, target_temp=62, status='active')
    db.session.add(step); db.session.commit()
    assert engine.facts(env.vessel, env.clock)['target'] == 65
    cfg = configuration.config(env.vessel);cfg['usage']='process'
    env.vessel.heating_config_json=cfg;db.session.commit()
    assert engine.facts(env.vessel, env.clock)['target'] == 62
    step.status='completed';db.session.commit()
    assert engine.facts(env.vessel, env.clock)['valid'] is False


def test_rule_validation_and_defaults_no_implicit_enabling(env):
    env.session.status='completed';db.session.commit()
    assert engine.DEFAULTS['enabled'] is False
    invalid = {**env.settings, 'expected_version':3, 'gap_hysteresis':2}
    with pytest.raises(configuration.HeatingError):
        engine.save_rule(env.vessel, invalid)
    other, foreign, mapping = _criar_plant_vessel_mapping(plant_name='Other', function_name='rule_demand')
    invalid = {**env.settings, 'expected_version':3, 'demand_mapping_id':mapping.id}
    with pytest.raises(configuration.HeatingError):
        engine.save_rule(env.vessel, invalid)
    cfg = {**env.settings, 'expected_version':3, 'require_demand':False, 'demand_mapping_id':None}
    engine.save_rule(env.vessel, cfg)
    env.session.status='active';db.session.commit()
    env.observed.pop(env.demand.external_id)
    assert trigger(env).context_json['demand_percent'] is None


def test_response_routes_scope_permission_and_rendering(env, app, client, monkeypatch):
    _login_admin(app, client)
    request = trigger(env)
    url = f'/brewstation/plant-workspace/{env.plant.id}/vessels/{env.vessel.id}/heating/requests/{request.id}/respond'
    from model.core.user import User
    original = User.has_permission
    monkeypatch.setattr(User, 'has_permission', lambda self, code: False if code=='brew_sessions.update' else original(self, code))
    assert client.post(url, json={'action':'acknowledge'}).status_code == 403
    monkeypatch.setattr(User, 'has_permission', original)
    assert client.post(url.replace(f'/vessels/{env.vessel.id}/', '/vessels/99999/'), json={'action':'acknowledge'}).status_code == 404
    assert client.post(url, json={'action':'acknowledge'}).status_code == 200
    assert client.post(url, json={'action':'decline'}).status_code == 409
    page=client.get(f'/brewstation/plant-workspace/{env.plant.id}/tab/plant')
    assert page.status_code==200 and b'minimum_seconds' in page.data and b'heatingDemand' in page.data
    layout=DashboardLayout(name='Advisory', plant_id=env.plant.id)
    db.session.add(layout);db.session.commit()
    runtime.create_widget_from_editor(layout,widget_type='heating',label_text='HLT',x=0,y=0,vessel_id=env.vessel.id)
    page=client.get(f'/brewstation/dashboards/{layout.id}/view')
    assert page.status_code==200 and b'canRespondHeating = true' in page.data


def test_received_event_creates_requests_without_browser_and_commands_are_not_observations(app, monkeypatch):
    # Real observation ingress & EventBus, independent of mock DTOs used in engine tests.
    from core.event_bus import event_bus
    with app.app_context():
        actor=_criar_actor(name='ingress', function_name='ingress', unit='%')
        events=[]
        def received(function_name=None): events.append(function_name)
        event_bus.subscribe('device_manager.actor.observation_received', received)
        try:
            assert device_service.get_observation(actor.external_id) is None
            device_service.set_value(actor.external_id, 90, publish=False)
            assert device_service.get_observation(actor.external_id) is None and events==[]
            device_service.update_from_mqtt(actor, 80)
            observed=device_service.get_observation(actor.external_id)
            assert observed['value']==80 and observed['source']=='mqtt_state' and events==['ingress']
            device_service.set_value(actor.external_id, 99, publish=False)
            assert device_service.get_observation(actor.external_id)==observed
        finally:
            event_bus._listeners['device_manager.actor.observation_received'].remove(received)


def test_observation_listener_and_sweep_do_not_need_dashboard(env):
    for second in (0,5,10):
        env.sample(second)
        engine.on_observation(function_name='rule_temp')
    assert HeatingRequest.query.count()==1
    env.session.status='paused';db.session.commit()
    engine.sweep()
    assert HeatingRequest.query.one().status=='cancelled'


def test_migration_is_additive_and_preserves_audit():
    path=Path(__file__).resolve().parents[1]/'migrations/versions/c18f7d23a904_heating_operator_requests.py'
    spec=importlib.util.spec_from_file_location('heating_requests_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with sa.create_engine('sqlite://').begin() as connection:
        connection.execute(sa.text(f'CREATE TABLE "{migration.VESSEL}" (id INTEGER PRIMARY KEY, label TEXT)'))
        connection.execute(sa.text(f'CREATE TABLE "{migration.SESSION}" (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text(f'INSERT INTO "{migration.VESSEL}" VALUES (1, \'Old HLT\')'))
        migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade();migration.upgrade()
        assert connection.execute(sa.text(f'SELECT label FROM "{migration.VESSEL}"')).scalar()=='Old HLT'
        migration.downgrade();migration.upgrade()
        table=sa.Table(migration.REQUEST,sa.MetaData(),autoload_with=connection)
        now=datetime.now(timezone.utc)
        connection.execute(table.insert().values(vessel_id=1,session_id=1,source_id='source',status='requested',
            created_at=now,updated_at=now,expires_at=now,context_json={}))
        with pytest.raises(RuntimeError,match='Downgrade bloqueado'):
            migration.downgrade()
        assert connection.execute(sa.select(sa.func.count()).select_from(table)).scalar()==1


def test_real_received_events_evaluate_without_ui(env, monkeypatch):
    import addons.addon_device_manager.root.services.device_service as devices
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return env.clock
    monkeypatch.setattr(devices, 'datetime', Clock)
    monkeypatch.setattr(devices, 'get_observation', REAL_GET_OBSERVATION)
    for second in (0, 5, 10):
        env.sample(second)
        devices.update_from_mqtt(env.sensor, 60)
        devices.update_from_mqtt(env.demand, 95)
    assert HeatingRequest.query.count() == 1
    assert HeatingRequest.query.one().context_json['demand_percent'] == 95


def test_pause_lifecycle_reconciles_without_next_sensor_message(env):
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    trigger(env)
    recipe_timeline_service.toggle_pause_session(env.session)
    assert HeatingRequest.query.one().status == 'cancelled'


def test_adjusting_target_cancels_old_step_context_immediately(env):
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    cfg=configuration.config(env.vessel); cfg['usage']='process'
    env.vessel.heating_config_json=cfg
    step=BrewSessionStep(session_id=env.session.id, vessel_id=env.vessel.id, name='Mash', step_index=1, target_temp=65, status='active')
    db.session.add(step);db.session.commit()
    trigger(env)
    recipe_timeline_service.adjust_session_step(step.id, field='target_temp', new_value=70, user_id=1)
    assert HeatingRequest.query.one().status=='cancelled'


def test_empty_audit_table_is_preserved_when_runtime_blocks_downgrade():
    path=Path(__file__).resolve().parents[1]/'migrations/versions/c18f7d23a904_heating_operator_requests.py'
    spec=importlib.util.spec_from_file_location('heating_guard_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with sa.create_engine('sqlite://').begin() as connection:
        connection.execute(sa.text(f'CREATE TABLE "{migration.VESSEL}" (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text(f'CREATE TABLE "{migration.SESSION}" (id INTEGER PRIMARY KEY)'))
        migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade()
        connection.execute(sa.text(f'INSERT INTO "{migration.VESSEL}" (id, heating_runtime_json) VALUES (1, :value)'), {'value':'{}'})
        with pytest.raises(RuntimeError,match='Downgrade bloqueado'):
            migration.downgrade()
        assert sa.inspect(connection).has_table(migration.REQUEST)


def test_worker_started_before_request_does_not_invalidate_it(env, app):
    request = trigger(env)
    original = engine.aware(app.config['HEATING_RUNTIME_STARTED_AT'])
    app.config['HEATING_RUNTIME_STARTED_AT'] = (original+timedelta(milliseconds=1)).isoformat()
    evaluate(env, 11)
    engine.respond(env.vessel, request.id, 'acknowledge', 1, env.clock)
    db.session.refresh(request)
    assert request.status == 'acknowledged'


def test_restart_discards_old_candidate_time(env, app):
    evaluate(env, 0)
    evaluate(env, 5)
    app.config['HEATING_RUNTIME_STARTED_AT'] = (env.clock+timedelta(seconds=1)).isoformat()
    evaluate(env, 10)
    evaluate(env, 15)
    assert HeatingRequest.query.count() == 0
    evaluate(env, 20)
    assert HeatingRequest.query.count() == 1


def test_runtime_cannot_be_overwritten_by_generic_vessel_crud(env):
    from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_vessel_service import BrewPlantVesselService
    trigger(env)
    before=deepcopy(env.vessel.heating_runtime_json)
    BrewPlantVesselService()._apply_fields(env.vessel, {'heating_runtime_json': {}})
    assert env.vessel.heating_runtime_json == before


def test_migration_accepts_current_orm_schema_without_duplicate_indexes(app):
    path=Path(__file__).resolve().parents[1]/'migrations/versions/c18f7d23a904_heating_operator_requests.py'
    spec=importlib.util.spec_from_file_location('heating_metadata_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with app.app_context():
        bind=db.session.connection()
        before=sa.inspect(bind).get_indexes(migration.REQUEST)
        migration.op=Operations(MigrationContext.configure(bind))
        migration.upgrade()
        assert sa.inspect(bind).get_indexes(migration.REQUEST)==before


@pytest.mark.parametrize('target', ['request', 'vessel', 'session'])
def test_audit_and_referenced_parents_cannot_be_permanently_deleted(env, target):
    request=trigger(env)
    item={'request':request,'vessel':env.vessel,'session':env.session}[target]
    db.session.delete(item)
    with pytest.raises(ValueError,match='aquecimento'):
        db.session.commit()
    db.session.rollback()
    assert HeatingRequest.query.count()==1


def test_disabled_rule_cleans_pending_once_then_stops_processing_observations(env, monkeypatch):
    trigger(env)
    cfg=configuration.config(env.vessel);cfg['rule']['enabled']=False
    env.vessel.heating_config_json=cfg;db.session.commit()
    engine.on_observation(function_name='rule_temp')
    assert HeatingRequest.query.one().status=='cancelled'
    assert env.vessel.heating_runtime_json is None
    def forbidden(*args, **kwargs): pytest.fail('Disabled rule unnecessarily evaluated')
    monkeypatch.setattr(engine, 'evaluate', forbidden)
    engine.on_observation(function_name='rule_temp')
    assert engine.sweep()==0
