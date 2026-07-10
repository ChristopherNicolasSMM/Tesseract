"""
tests/test_dashboard_runtime.py

Cobre a arquitetura de Dashboard de Brassagem consolidada em conversa
— ponto de encontro entre addon_device_manager e mash_control:
- dashboard_reading_logger.py: grava leitura em BrewSessionLog só
  quando existe Sessão de Brassagem ativa pra planta daquele sensor,
  com throttle.
- dashboard_runtime_service.py: snapshot (valor atual de todos os
  widgets de um layout), acionamento de atuador, conexões de
  tubulação (BrewPlant.plant_schema_json), leituras históricas.
- controller/dashboard_runtime.py: rotas view/snapshot/set-value/readings.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_service
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.services import dashboard_runtime_service as svc


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


def _criar_actor(*, name, function_name, category="sensor", actor_type="sensor", unit=None, icon=None):
    function = DeviceFunction.query.filter_by(name=function_name).first()
    if function is None:
        function = DeviceFunction(name=function_name, display_name=function_name, category=category, unit=unit, icon=icon)
        db.session.add(function)
        db.session.commit()

    device = DeviceMetadata(name=f"device_{name}")
    db.session.add(device)
    db.session.commit()

    actor = DeviceActor(device_id=device.id, port_name="GPIO1", function_id=function.id, actor_type=actor_type, name=name)
    db.session.add(actor)
    db.session.commit()
    return actor


def _criar_plant_vessel_mapping(*, plant_name="Planta Teste", vessel_label="Mash Tun",
                                 role_key="sensor_temp", function_name="mash_temp"):
    plant = BrewPlant(name=plant_name)
    db.session.add(plant)
    db.session.commit()

    vessel = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text=vessel_label)
    db.session.add(vessel)
    db.session.commit()

    mapping = BrewPlantMapping(vessel_id=vessel.id, role_key=role_key, device_function_name=function_name)
    db.session.add(mapping)
    db.session.commit()
    return plant, vessel, mapping


# ── Logger de leitura (BrewSessionLog source="sensor") ──────────────────────

def test_logger_grava_leitura_com_sessao_ativa(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping()
        session = BrewSession(name="Sessão 1", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        sensor = _criar_actor(name="temp_sensor", function_name="mash_temp")
        device_service.update_from_mqtt(sensor, 65.5)

        logs = BrewSessionLog.query.filter_by(session_id=session.id, source="sensor").all()
        assert len(logs) == 1
        assert logs[0].detail_json["function_name"] == "mash_temp"
        assert logs[0].detail_json["value"] == 65.5


def test_logger_nao_grava_sem_sessao_ativa(app):
    with app.app_context():
        _criar_plant_vessel_mapping()
        sensor = _criar_actor(name="temp_sensor2", function_name="mash_temp2")
        device_service.update_from_mqtt(sensor, 65.5)

        assert BrewSessionLog.query.filter_by(source="sensor").count() == 0


def test_logger_respeita_throttle(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(function_name="mash_temp3")
        session = BrewSession(name="Sessão 2", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        sensor = _criar_actor(name="temp_sensor3", function_name="mash_temp3")
        device_service.update_from_mqtt(sensor, 60.0)
        device_service.update_from_mqtt(sensor, 61.0)  # dentro da janela de throttle

        logs = BrewSessionLog.query.filter_by(session_id=session.id, source="sensor").all()
        assert len(logs) == 1  # só a primeira gravou


def test_logger_ignora_sessao_de_outra_planta(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(function_name="mash_temp4")
        outra_plant = BrewPlant(name="Outra Planta")
        db.session.add(outra_plant)
        db.session.commit()
        session_outra = BrewSession(name="Sessão Outra", plant_id=outra_plant.id, status="active")
        db.session.add(session_outra)
        db.session.commit()

        sensor = _criar_actor(name="temp_sensor4", function_name="mash_temp4")
        device_service.update_from_mqtt(sensor, 60.0)

        assert BrewSessionLog.query.filter_by(source="sensor").count() == 0


# ── Snapshot (valor atual de todos os widgets) ──────────────────────────────

def test_snapshot_widget_simples(app):
    with app.app_context():
        _criar_actor(name="hlt_temp_actor", function_name="hlt_temp", unit="°C", icon="bi-thermometer")
        actor = DeviceActor.query.filter_by(name="hlt_temp_actor").first()
        device_service.set_value(actor.external_id, 68.4)

        layout = DashboardLayout(name="Layout Teste")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="digital", label_text="HLT",
                                  device_function_name="hlt_temp")
        db.session.add(widget)
        db.session.commit()

        snap = svc.get_layout_snapshot(layout)
        assert snap["widgets"][widget.id]["value"] == 68.4
        assert snap["widgets"][widget.id]["unit"] == "°C"


def test_snapshot_widget_vessel_reaproveita_plant_mapping(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(function_name="mash_temp_vessel")
        _criar_actor(name="mash_temp_actor", function_name="mash_temp_vessel")
        actor = DeviceActor.query.filter_by(name="mash_temp_actor").first()
        device_service.set_value(actor.external_id, 63.1)

        layout = DashboardLayout(name="Layout Vessel", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id, label_text="Mash Tun")
        db.session.add(widget)
        db.session.commit()

        snap = svc.get_layout_snapshot(layout)
        roles = snap["widgets"][widget.id]["roles"]
        assert roles["sensor_temp"]["value"] == 63.1


# ── Acionar atuador (toggle / vessel+role_key) ───────────────────────────────

def test_set_widget_value_widget_simples(app):
    with app.app_context():
        _criar_actor(name="bomba1_actor", function_name="bomba1", category="actuator", actor_type="actuator")
        layout = DashboardLayout(name="L")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", device_function_name="bomba1")
        db.session.add(widget)
        db.session.commit()

        ok = svc.set_widget_value(widget, True)
        assert ok is True
        assert device_service.get_value("bomba1_actor") is True


def test_set_widget_value_vessel_com_role_key(app):
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping(
            role_key="actor_heat", function_name="resistencia1",
        )
        _criar_actor(name="resistencia1_actor", function_name="resistencia1", category="actuator", actor_type="actuator")

        layout = DashboardLayout(name="L2", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id)
        db.session.add(widget)
        db.session.commit()

        ok = svc.set_widget_value(widget, True, role_key="actor_heat")
        assert ok is True
        assert device_service.get_value("resistencia1_actor") is True


def test_set_widget_value_role_key_inexistente_falha(app):
    with app.app_context():
        plant, vessel, _ = _criar_plant_vessel_mapping(function_name="mash_temp5")
        layout = DashboardLayout(name="L3", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id)
        db.session.add(widget)
        db.session.commit()

        ok = svc.set_widget_value(widget, True, role_key="actor_nao_existe")
        assert ok is False


# ── Conexões de tubulação (plant_schema_json) ────────────────────────────────

def test_get_plant_connections_resolve_flowing(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Pipes")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash Tun")
        db.session.add_all([v1, v2])
        db.session.commit()

        plant.plant_schema_json = {
            "connections": [{"from_vessel_id": v1.id, "to_vessel_id": v2.id, "flow_function_name": "bomba_transfer"}]
        }
        db.session.commit()

        _criar_actor(name="bomba_transfer_actor", function_name="bomba_transfer", category="actuator", actor_type="actuator")
        device_service.set_value("bomba_transfer_actor", True)

        layout = DashboardLayout(name="L4", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()

        connections = svc.get_plant_connections(layout)
        assert len(connections) == 1
        assert connections[0]["flowing"] is True


def test_get_plant_connections_sem_plant_id_retorna_vazio(app):
    with app.app_context():
        layout = DashboardLayout(name="L5")
        db.session.add(layout)
        db.session.commit()
        assert svc.get_plant_connections(layout) == []


# ── Leituras históricas ──────────────────────────────────────────────────────

def test_get_session_readings_filtra_por_function_e_janela(app):
    with app.app_context():
        plant = BrewPlant(name="Planta Chart")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S Chart", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        agora = datetime.now(timezone.utc)
        db.session.add(BrewSessionLog(
            session_id=session.id, source="sensor", message="m",
            detail_json={"function_name": "mash_temp", "value": 60.0},
            created_at=agora - timedelta(minutes=5),
        ))
        db.session.add(BrewSessionLog(
            session_id=session.id, source="sensor", message="m",
            detail_json={"function_name": "outra_funcao", "value": 99.0},
            created_at=agora - timedelta(minutes=5),
        ))
        db.session.add(BrewSessionLog(
            session_id=session.id, source="sensor", message="m",
            detail_json={"function_name": "mash_temp", "value": 61.0},
            created_at=agora - timedelta(minutes=120),  # fora da janela padrão de 60min
        ))
        db.session.commit()

        result = svc.get_session_readings(session.id, "mash_temp", window_minutes=60)
        assert len(result["points"]) == 1
        assert result["points"][0]["v"] == 60.0


# ── Rotas web ────────────────────────────────────────────────────────────────

def test_index_redireciona_pro_layout_default(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="Padrão", is_default=True)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get("/brewstation/dashboards/", follow_redirects=False)
    assert resp.status_code == 302
    assert f"/brewstation/dashboards/{layout_id}/view" in resp.headers["Location"]


def test_view_renderiza_widgets(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="View Teste")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="digital", label_text="HLT Temp")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    assert resp.status_code == 200
    assert b"HLT Temp" in resp.data
    assert b"db-widget-" in resp.data


def test_snapshot_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="Snap Teste")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "widgets" in body
    assert "connections" in body


def test_set_value_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_actor(name="valvula1_actor", function_name="valvula1", category="actuator", actor_type="actuator")
        layout = DashboardLayout(name="SV Teste")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", device_function_name="valvula1")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/set-value", json={"value": True})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    with app.app_context():
        assert device_service.get_value("valvula1_actor") is True


def test_readings_rota_web_exige_function_name(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta R")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S R", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.get(f"/brewstation/dashboards/sessions/{session_id}/readings")
    assert resp.status_code == 400
