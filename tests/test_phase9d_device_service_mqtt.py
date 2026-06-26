"""
tests/test_phase9d_device_service_mqtt.py

Cobre a Fase D (docs/skills/05-proposta-addon-device-manager-e-mqtt.md):
device_service.py (API get_value/set_value/on_change) e a montagem do
payload de LWT agregado em mqtt_client_service.py (build_lwt_payload),
sem depender de um broker MQTT real — só a lógica pura é testada aqui;
o fluxo de rede de fato pertence à Fase F (validação ponta a ponta com
tesseract-device-bridge).
"""
import json

import pytest

from core.app_factory import create_app
from core.db import db
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_service
from addons.addon_device_manager.root.services import mqtt_client_service


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def _criar_actor(app, *, name, is_risk=False, failsafe_value=None, mqtt_config=None):
    function = DeviceFunction(name=f"func_{name}", display_name=name, category="actuator")
    db.session.add(function)
    db.session.commit()

    device = DeviceMetadata(name=f"device_{name}")
    db.session.add(device)
    db.session.commit()

    actor = DeviceActor(
        device_id=device.id, port_name="GPIO1", function_id=function.id,
        actor_type="actuator", name=name, is_risk=is_risk, failsafe_value=failsafe_value,
    )
    if mqtt_config:
        actor.set_config({"mqtt_config": mqtt_config})
    db.session.add(actor)
    db.session.commit()
    return actor


def test_set_value_e_get_value_via_external_id(app):
    with app.app_context():
        actor = _criar_actor(app, name="heater_test")

        ok = device_service.set_value(actor.external_id, 85, publish=False)
        assert ok is True

        assert device_service.get_value(actor.external_id) == 85


def test_get_value_via_name_tambem_funciona(app):
    with app.app_context():
        actor = _criar_actor(app, name="pump_test")
        device_service.set_value(actor.name, True, publish=False)
        assert device_service.get_value(actor.name) is True


def test_get_value_actor_inexistente_retorna_none(app):
    with app.app_context():
        assert device_service.get_value("nao-existe-external-id") is None


def test_set_value_actor_inexistente_retorna_false(app):
    with app.app_context():
        assert device_service.set_value("nao-existe", 1) is False


def test_on_change_e_disparado_no_set_value(app):
    with app.app_context():
        actor = _criar_actor(app, name="sensor_callback_test")
        valores_recebidos = []

        device_service.on_change(actor.external_id, valores_recebidos.append)
        device_service.set_value(actor.external_id, 42.0, publish=False)

        assert valores_recebidos == [42.0]


def test_set_value_publish_sem_cliente_mqtt_nao_quebra(app):
    """
    publish=True (default) mas sem cliente MQTT ativo (sem broker em
    teste) — não deve levantar exceção, só ignora a publicação.
    """
    with app.app_context():
        actor = _criar_actor(
            app, name="actuator_no_broker",
            mqtt_config={"command_topic": "actuators/x/set"},
        )
        ok = device_service.set_value(actor.external_id, 50)
        assert ok is True


def test_build_lwt_payload_inclui_apenas_atuadores_de_risco_com_topico(app):
    with app.app_context():
        risco_com_topico = _criar_actor(
            app, name="risco_com_topico", is_risk=True, failsafe_value="0",
            mqtt_config={"command_topic": "actuators/risco_com_topico/set"},
        )
        _criar_actor(app, name="risco_sem_topico", is_risk=True, failsafe_value="0")  # sem mqtt_config
        _criar_actor(app, name="sem_risco", is_risk=False)

        payload = json.loads(mqtt_client_service.build_lwt_payload(app))

        assert payload["status"] == "offline"
        external_ids = [a["external_id"] for a in payload["failsafe_actuators"]]
        assert external_ids == [risco_com_topico.external_id]
        assert payload["failsafe_actuators"][0]["failsafe_value"] == "0"
        assert payload["failsafe_actuators"][0]["command_topic"].endswith(
            "actuators/risco_com_topico/set"
        )


def test_build_lwt_payload_vazio_quando_nenhum_atuador_de_risco(app):
    with app.app_context():
        _criar_actor(app, name="normal", is_risk=False)
        payload = json.loads(mqtt_client_service.build_lwt_payload(app))
        assert payload["failsafe_actuators"] == []


def test_status_topic_usa_topic_prefix_do_env(app, monkeypatch):
    monkeypatch.setenv("MQTT_TOPIC_PREFIX", "brewery")
    assert mqtt_client_service.status_topic() == "brewery/system/tesseract/status"
