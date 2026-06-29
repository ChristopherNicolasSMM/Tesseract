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
