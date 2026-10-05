"""
tests/test_phase9f_automation_engine.py

Cobre o motor de automação reativo (Fase E, Opção 1 — decisão de
2026-06-29): sensor -> condição -> ator, disparado via EventBus do
Core (core/event_bus.py, evento "device_manager.actor.value_changed"),
sem polling/scheduler. Mecanismo corrigido na Fase G (ver
automation_engine.py) — versão original da Fase E usava um callback
paralelo próprio em vez do EventBus já existente no projeto.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_service
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule_log import AutomationRuleLog


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _criar_actor(*, name, function_name, category="sensor", actor_type="sensor"):
    function = DeviceFunction.query.filter_by(name=function_name).first()
    if function is None:
        function = DeviceFunction(name=function_name, display_name=function_name, category=category)
        db.session.add(function)
        db.session.commit()

    device = DeviceMetadata(name=f"device_{name}")
    db.session.add(device)
    db.session.commit()

    actor = DeviceActor(
        device_id=device.id, port_name="GPIO1", function_id=function.id,
        actor_type=actor_type, name=name,
    )
    db.session.add(actor)
    db.session.commit()
    return actor


def _criar_rule(*, sensor_function_name, actor_function_name, operator="<=",
                 value=65.0, action="ON", actor_value=None, cooldown=30):
    rule = AutomationRule(
        name=f"Regra {sensor_function_name}->{actor_function_name}",
        sensor_function_name=sensor_function_name,
        condition_operator=operator, condition_value=value,
        actor_function_name=actor_function_name, actor_action=action,
        actor_value=actor_value, cooldown_seconds=cooldown,
    )
    db.session.add(rule)
    db.session.commit()
    return rule


def test_regra_dispara_quando_condicao_e_satisfeita(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor", function_name="mash_temp", category="sensor")
        _criar_actor(name="heater", function_name="mash_heater", category="actuator", actor_type="actuator")
        rule = _criar_rule(sensor_function_name="mash_temp", actor_function_name="mash_heater",
                            operator="<=", value=65.0, action="ON")

        device_service.update_from_mqtt(sensor, 60.0)  # 60 <= 65 -> dispara

        db.session.refresh(rule)
        assert rule.trigger_count == 1
        assert rule.last_triggered_at is not None

        log = AutomationRuleLog.query.filter_by(rule_id=rule.id).first()
        assert log is not None
        assert log.success is True
        assert log.sensor_value_at_trigger == 60.0
        assert device_service.get_value("heater") is True


def test_regra_nao_dispara_quando_condicao_nao_e_satisfeita(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor2", function_name="mash_temp2")
        _criar_actor(name="heater2", function_name="mash_heater2", actor_type="actuator")
        rule = _criar_rule(sensor_function_name="mash_temp2", actor_function_name="mash_heater2",
                            operator="<=", value=65.0)

        device_service.update_from_mqtt(sensor, 70.0)  # 70 <= 65 é falso

        db.session.refresh(rule)
        assert rule.trigger_count in (0, None)
        assert AutomationRuleLog.query.filter_by(rule_id=rule.id).count() == 0


def test_cooldown_impede_disparo_repetido(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor3", function_name="mash_temp3")
        _criar_actor(name="heater3", function_name="mash_heater3", actor_type="actuator")
        rule = _criar_rule(sensor_function_name="mash_temp3", actor_function_name="mash_heater3",
                            operator="<=", value=65.0, cooldown=9999)

        device_service.update_from_mqtt(sensor, 60.0)
        device_service.update_from_mqtt(sensor, 59.0)  # ainda dentro do cooldown

        db.session.refresh(rule)
        assert rule.trigger_count == 1
        assert AutomationRuleLog.query.filter_by(rule_id=rule.id).count() == 1


def test_action_off(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor4", function_name="mash_temp4")
        _criar_actor(name="heater4", function_name="mash_heater4", actor_type="actuator")
        device_service.set_value("heater4", True, publish=False)
        _criar_rule(sensor_function_name="mash_temp4", actor_function_name="mash_heater4",
                    operator=">=", value=68.0, action="OFF")

        device_service.update_from_mqtt(sensor, 70.0)

        assert device_service.get_value("heater4") is False


def test_action_set_value(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor5", function_name="mash_temp5")
        _criar_actor(name="heater5", function_name="mash_heater5", actor_type="actuator")
        _criar_rule(sensor_function_name="mash_temp5", actor_function_name="mash_heater5",
                    operator="<=", value=65.0, action="SET_VALUE", actor_value=85.0)

        device_service.update_from_mqtt(sensor, 60.0)

        assert device_service.get_value("heater5") == 85.0


def test_action_toggle(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor6", function_name="mash_temp6")
        _criar_actor(name="pump6", function_name="mash_pump6", actor_type="actuator")
        device_service.set_value("pump6", False, publish=False)
        _criar_rule(sensor_function_name="mash_temp6", actor_function_name="mash_pump6",
                    operator="==", value=100.0, action="TOGGLE")

        device_service.update_from_mqtt(sensor, 100.0)

        assert device_service.get_value("pump6") is True


def test_valor_nao_numerico_e_ignorado_sem_quebrar(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor7", function_name="mash_temp7")
        _criar_actor(name="heater7", function_name="mash_heater7", actor_type="actuator")
        rule = _criar_rule(sensor_function_name="mash_temp7", actor_function_name="mash_heater7")

        # Não deve lançar exceção mesmo com valor não-numérico.
        device_service.update_from_mqtt(sensor, "erro_sensor")

        db.session.refresh(rule)
        assert rule.trigger_count in (0, None)


def test_actor_function_inexistente_gera_log_de_falha(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor8", function_name="mash_temp8")
        rule = _criar_rule(sensor_function_name="mash_temp8", actor_function_name="funcao_que_nao_existe")

        device_service.update_from_mqtt(sensor, 1.0)  # 1.0 <= 65.0 -> tenta disparar

        log = AutomationRuleLog.query.filter_by(rule_id=rule.id).first()
        assert log is not None
        assert log.success is False
        assert "funcao_que_nao_existe" in log.error_message


def test_regra_inativa_nunca_dispara(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor9", function_name="mash_temp9")
        _criar_actor(name="heater9", function_name="mash_heater9", actor_type="actuator")
        rule = _criar_rule(sensor_function_name="mash_temp9", actor_function_name="mash_heater9")
        rule.is_active = False
        db.session.commit()

        device_service.update_from_mqtt(sensor, 1.0)

        assert AutomationRuleLog.query.filter_by(rule_id=rule.id).count() == 0


def test_multiplas_regras_para_o_mesmo_sensor_disparam_juntas(app):
    with app.app_context():
        sensor = _criar_actor(name="temp_sensor10", function_name="mash_temp10")
        _criar_actor(name="heater10", function_name="mash_heater10", actor_type="actuator")
        _criar_actor(name="alarm10", function_name="mash_alarm10", actor_type="actuator")
        rule_a = _criar_rule(sensor_function_name="mash_temp10", actor_function_name="mash_heater10", action="ON")
        rule_b = _criar_rule(sensor_function_name="mash_temp10", actor_function_name="mash_alarm10", action="ON")

        device_service.update_from_mqtt(sensor, 1.0)

        db.session.refresh(rule_a)
        db.session.refresh(rule_b)
        assert rule_a.trigger_count == 1
        assert rule_b.trigger_count == 1
        assert device_service.get_value("heater10") is True
        assert device_service.get_value("alarm10") is True


@pytest.mark.parametrize('state', ['draft', 'paused', 'completed', 'aborted', 'deleted_session',
                                   'deleted_plant', 'missing_session', 'missing_plant', 'no_plant'])
def test_regra_vinculada_bloqueada_nao_aciona_nem_escreve(app, monkeypatch, state):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
    from addons.addon_brewstation.features.feature_mash_control.services import automation_engine
    with app.app_context():
        plant = BrewPlant(name="Planta guarda automação")
        db.session.add(plant)
        db.session.flush()
        session = BrewSession(name="Sessão guarda", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.flush()
        rule = _criar_rule(sensor_function_name="sensor_guarda", actor_function_name="ator_guarda")
        rule.session_id = session.id
        if state in ('draft', 'paused', 'completed', 'aborted'):
            session.status = state
        elif state == 'deleted_session':
            session.is_deleted = True
        elif state == 'deleted_plant':
            plant.is_deleted = True
        elif state == 'no_plant':
            session.plant_id = None
        db.session.commit()
        # Simula referências órfãs sem inserir dados inválidos ou desativar FKs.
        original_get = db.session.get
        def scoped_get(model, identity, **kwargs):
            if state == 'missing_session' and model is BrewSession:
                return None
            if state == 'missing_plant' and model is BrewPlant:
                return None
            return original_get(model, identity, **kwargs)
        monkeypatch.setattr(db.session, 'get', scoped_get)
        def forbidden(*args, **kwargs):
            pytest.fail('Regra bloqueada não pode acionar dispositivo ou resolver ação')
        monkeypatch.setattr(device_service, 'set_value', forbidden)
        monkeypatch.setattr(automation_engine, '_resolve_target_value', forbidden)
        before = (rule.trigger_count, rule.last_triggered_at, AutomationRuleLog.query.count())
        automation_engine._on_device_value_changed(function_name="sensor_guarda", value=1)
        assert (rule.trigger_count, rule.last_triggered_at, AutomationRuleLog.query.count()) == before
        assert session.status == (state if state in ('draft', 'paused', 'completed', 'aborted') else 'active')


def test_regra_vinculada_pause_resume_preserva_cooldown_e_historico(app):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
    with app.app_context():
        sensor = _criar_actor(name="sensor_session_guard", function_name="sensor_session_guard")
        _criar_actor(name="heater_session_guard", function_name="heater_session_guard",
                     category="actuator", actor_type="actuator")
        plant = BrewPlant(name="Planta runtime")
        db.session.add(plant)
        db.session.flush()
        from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
        from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
        vessel = BrewPlantVessel(plant_id=plant.id, label_text="Tanque runtime", vessel_type="mash_tun")
        db.session.add(vessel)
        db.session.flush()
        db.session.add_all([
            BrewPlantMapping(vessel_id=vessel.id, role_key="sensor_temp", device_function_name="sensor_session_guard"),
            BrewPlantMapping(vessel_id=vessel.id, role_key="actor_heat", device_function_name="heater_session_guard"),
        ])
        session = BrewSession(name="Sessão runtime", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.flush()
        rule = _criar_rule(sensor_function_name="sensor_session_guard", actor_function_name="heater_session_guard",
                           action="ON", cooldown=0)
        rule.session_id = session.id
        db.session.commit()
        device_service.update_from_mqtt(sensor, 1)
        db.session.refresh(rule)
        assert rule.trigger_count == 1
        first_trigger = rule.last_triggered_at
        session.status = 'paused'
        db.session.commit()
        device_service.update_from_mqtt(sensor, 2)
        db.session.refresh(rule)
        assert rule.trigger_count == 1 and rule.last_triggered_at == first_trigger
        assert device_service.get_value('heater_session_guard') is True  # Pausar não desliga.
        session.status = 'active'
        db.session.commit()
        device_service.update_from_mqtt(sensor, 3)
        db.session.refresh(rule)
        assert rule.trigger_count == 2
        assert AutomationRuleLog.query.filter_by(rule_id=rule.id).count() == 2
        rule.cooldown_seconds = 9999
        db.session.commit()
        device_service.update_from_mqtt(sensor, 4)
        db.session.refresh(rule)
        assert rule.trigger_count == 2


@pytest.mark.parametrize('invalid', ['unmapped_sensor', 'unmapped_actor', 'shared_sensor', 'shared_actor',
                                    'deleted_mapping', 'deleted_vessel', 'duplicate_sensor',
                                    'duplicate_actor', 'deleted_function'])
def test_regra_vinculada_exige_funcoes_exclusivas_e_atores_unicos(app, monkeypatch, invalid):
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
    from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
    from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
    from addons.addon_brewstation.features.feature_mash_control.services import automation_engine
    with app.app_context():
        _criar_actor(name='isolation_sensor', function_name='isolation_sensor')
        _criar_actor(name='isolation_actor', function_name='isolation_actor', category='actuator', actor_type='actuator')
        plant = BrewPlant(name='Planta isolada')
        other = BrewPlant(name='Planta externa')
        db.session.add_all([plant, other])
        db.session.flush()
        vessel = BrewPlantVessel(plant_id=plant.id, label_text='Tanque', vessel_type='mash_tun')
        external = BrewPlantVessel(plant_id=other.id, label_text='Tanque externo', vessel_type='mash_tun')
        db.session.add_all([vessel, external])
        db.session.flush()
        for role, name in [('sensor_temp', 'isolation_sensor'), ('actor_heat', 'isolation_actor')]:
            if invalid == 'unmapped_sensor' and role == 'sensor_temp' or invalid == 'unmapped_actor' and role == 'actor_heat':
                continue
            db.session.add(BrewPlantMapping(vessel_id=vessel.id, role_key=role, device_function_name=name,
                                           is_deleted=invalid == 'deleted_mapping'))
        if invalid.startswith('shared_'):
            name = 'isolation_sensor' if invalid == 'shared_sensor' else 'isolation_actor'
            db.session.add(BrewPlantMapping(vessel_id=external.id, role_key='sensor_temp', device_function_name=name))
        vessel.is_deleted = invalid == 'deleted_vessel'
        session = BrewSession(name='Sessão isolada', plant_id=plant.id, status='active')
        db.session.add(session)
        db.session.flush()
        rule = _criar_rule(sensor_function_name='isolation_sensor', actor_function_name='isolation_actor')
        rule.session_id = session.id
        db.session.commit()
        if invalid.startswith('duplicate_'):
            name = 'isolation_sensor' if invalid == 'duplicate_sensor' else 'isolation_actor'
            _criar_actor(name='duplicate_isolation', function_name=name)
        if invalid == 'deleted_function':
            DeviceFunction.query.filter_by(name='isolation_sensor').first().is_deleted = True
            db.session.commit()
        def forbidden(*args, **kwargs):
            pytest.fail('Função ausente/compartilhada/ambígua não pode acionar')
        monkeypatch.setattr(device_service, 'set_value', forbidden)
        automation_engine._on_device_value_changed(function_name='isolation_sensor', value=1)
        assert rule.trigger_count == 0
        assert rule.last_triggered_at is None
        assert AutomationRuleLog.query.filter_by(rule_id=rule.id).count() == 0


def test_resolvedor_publico_unico_exclui_apagados_e_nao_escolhe_primeiro(app):
    with app.app_context():
        first = _criar_actor(name='unique_first', function_name='unique_function')
        assert device_service.find_unique_actor_external_id_by_function_name('unique_function') == first.external_id
        second = _criar_actor(name='unique_second', function_name='unique_function')
        assert device_service.find_unique_actor_external_id_by_function_name('unique_function') is None
        second.is_deleted = True
        db.session.commit()
        assert device_service.find_unique_actor_external_id_by_function_name('unique_function') == first.external_id
        assert device_service.find_unique_actor_external_id_by_function_name('absent') is None
