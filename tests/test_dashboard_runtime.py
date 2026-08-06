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
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep
from addons.addon_brewstation.features.feature_mash_control.services import dashboard_runtime_service as svc
from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service as rt_svc


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

        result = svc.set_widget_value(widget, True)
        assert result["ok"] is True
        assert result["mqtt_connected"] is False  # sem broker rodando nos testes
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

        result = svc.set_widget_value(widget, True, role_key="actor_heat")
        assert result["ok"] is True
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

        result = svc.set_widget_value(widget, True, role_key="actor_nao_existe")
        assert result["ok"] is False
        assert result["error"]


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


# ── Editor visual (conversa — CraftBeerPi como referência) ──────────────────

def test_update_geometry_muda_posicao_e_tamanho(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Editor")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="digital", x=10, y=10, width=100, height=100)
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/geometry",
                        json={"x": 250, "y": 180, "width": 300, "height": 260})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert (widget.x, widget.y, widget.width, widget.height) == (250, 180, 300, 260)


def test_update_geometry_nao_deixa_colapsar_abaixo_de_40px(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Editor Min")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="digital", width=200, height=200)
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    client.post(f"/brewstation/dashboards/widgets/{widget_id}/geometry", json={"width": 5, "height": 5})
    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.width == 40
        assert widget.height == 40


def test_update_config_muda_label_e_mescla_config_json(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Config")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", label_text="Antigo",
                                  config_json={"svg_shape": "mash_tun", "manter": "isso"})
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={
        "label_text": "Mash Tun Novo", "config_json": {"svg_shape": "fermenter", "confirm_before_actuate": True},
    })
    assert resp.status_code == 200

    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.label_text == "Mash Tun Novo"
        assert widget.config_json["svg_shape"] == "fermenter"
        assert widget.config_json["confirm_before_actuate"] is True
        assert widget.config_json["manter"] == "isso"  # merge, não substitui tudo


def test_create_widget_via_editor(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Criar")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/widgets", json={
        "widget_type": "toggle", "label_text": "Bomba Nova", "x": 60, "y": 60,
        "device_function_name": "pump_x",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True

    with app.app_context():
        widget = DashboardWidget.query.get(body["widget_id"])
        assert widget.widget_type == "toggle"
        assert widget.label_text == "Bomba Nova"
        assert widget.device_function_name == "pump_x"


def test_create_widget_tipo_invalido_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Criar Invalido")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/widgets", json={
        "widget_type": "nao_existe", "label_text": "X", "x": 0, "y": 0,
    })
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_delete_widget_via_editor_e_soft_delete(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Remover")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="digital")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/delete")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.is_deleted is True
        assert widget.deleted_at is not None


def test_update_connections_sobrescreve_plant_schema_json(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Pipes Editor")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()
        layout = DashboardLayout(name="L Pipes", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id, v1_id, v2_id, plant_id = layout.id, v1.id, v2.id, plant.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/plant-connections", json={
        "connections": [{"from_vessel_id": v1_id, "to_vessel_id": v2_id, "flow_function_name": "bomba1", "color": "#ff0000", "width": 10}],
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        plant = BrewPlant.query.get(plant_id)
        conns = plant.plant_schema_json["connections"]
        assert len(conns) == 1
        assert conns[0]["color"] == "#ff0000"
        assert conns[0]["width"] == 10


def test_get_plant_connections_sem_anchor_waypoints_usa_default_retrocompativel(app):
    """Conexão salva antes do editor CAD-like (sem from_anchor/to_anchor/
    waypoints) continua funcionando — âncora vira o default (centro-base
    -> centro-topo, igual ao comportamento antigo) e waypoints vira []."""
    with app.app_context():
        plant = BrewPlant(name="Planta Legado")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()

        plant.plant_schema_json = {
            "connections": [{"from_vessel_id": v1.id, "to_vessel_id": v2.id}]
        }
        db.session.commit()

        layout = DashboardLayout(name="L Legado", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()

        connections = svc.get_plant_connections(layout)
        assert connections[0]["from_anchor"] == {"rx": 0.5, "ry": 1.0}
        assert connections[0]["to_anchor"] == {"rx": 0.5, "ry": 0.0}
        assert connections[0]["waypoints"] == []


def test_get_plant_connections_com_waypoints_e_anchor_customizada(app):
    with app.app_context():
        plant = BrewPlant(name="Planta CAD")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()

        plant.plant_schema_json = {
            "connections": [{
                "from_vessel_id": v1.id, "to_vessel_id": v2.id,
                "from_anchor": {"rx": 1.0, "ry": 0.5}, "to_anchor": {"rx": 0.0, "ry": 0.5},
                "waypoints": [{"x": 320, "y": 180}, {"x": 340, "y": 220}],
            }]
        }
        db.session.commit()

        layout = DashboardLayout(name="L CAD", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()

        connections = svc.get_plant_connections(layout)
        assert connections[0]["from_anchor"] == {"rx": 1.0, "ry": 0.5}
        assert connections[0]["to_anchor"] == {"rx": 0.0, "ry": 0.5}
        assert connections[0]["waypoints"] == [{"x": 320.0, "y": 180.0}, {"x": 340.0, "y": 220.0}]


def test_get_plant_connections_clampa_anchor_fora_da_faixa(app):
    """rx/ry fora de 0-1 (dado corrompido/bug de front) é clampado, nunca
    quebra o snapshot."""
    with app.app_context():
        plant = BrewPlant(name="Planta Clamp")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()

        plant.plant_schema_json = {
            "connections": [{
                "from_vessel_id": v1.id, "to_vessel_id": v2.id,
                "from_anchor": {"rx": 5.0, "ry": -3.0},
            }]
        }
        db.session.commit()

        layout = DashboardLayout(name="L Clamp", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()

        connections = svc.get_plant_connections(layout)
        assert connections[0]["from_anchor"] == {"rx": 1.0, "ry": 0.0}


def test_update_connections_persiste_anchor_e_waypoints(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Pipes CAD")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()
        layout = DashboardLayout(name="L Pipes CAD", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id, v1_id, v2_id, plant_id = layout.id, v1.id, v2.id, plant.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/plant-connections", json={
        "connections": [{
            "from_vessel_id": v1_id, "to_vessel_id": v2_id,
            "from_anchor": {"rx": 0.2, "ry": 0.8}, "to_anchor": {"rx": 0.9, "ry": 0.1},
            "waypoints": [{"x": 100, "y": 50}],
        }],
    })
    assert resp.status_code == 200

    with app.app_context():
        plant = BrewPlant.query.get(plant_id)
        conn = plant.plant_schema_json["connections"][0]
        assert conn["from_anchor"] == {"rx": 0.2, "ry": 0.8}
        assert conn["to_anchor"] == {"rx": 0.9, "ry": 0.1}
        assert conn["waypoints"] == [{"x": 100.0, "y": 50.0}]


def test_update_connections_ignora_waypoint_malformado(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Pipes Malformado")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash")
        db.session.add_all([v1, v2])
        db.session.commit()
        layout = DashboardLayout(name="L Pipes Malformado", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id, v1_id, v2_id, plant_id = layout.id, v1.id, v2.id, plant.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/plant-connections", json={
        "connections": [{
            "from_vessel_id": v1_id, "to_vessel_id": v2_id,
            "waypoints": [{"x": 100, "y": 50}, {"x": "não é número"}, "lixo"],
        }],
    })
    assert resp.status_code == 200

    with app.app_context():
        plant = BrewPlant.query.get(plant_id)
        conn = plant.plant_schema_json["connections"][0]
        assert conn["waypoints"] == [{"x": 100.0, "y": 50.0}]


def test_update_connections_sem_plant_id_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Sem Planta")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.post(f"/brewstation/dashboards/{layout_id}/plant-connections", json={"connections": []})
    assert resp.status_code == 400


def test_snapshot_expoe_color_e_width_da_conexao(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Snapshot Pipes")
        db.session.add(plant)
        db.session.commit()
        v1 = BrewPlantVessel(plant_id=plant.id, vessel_type="hlt", label_text="HLT2")
        v2 = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash2")
        db.session.add_all([v1, v2])
        db.session.commit()
        plant.plant_schema_json = {"connections": [
            {"from_vessel_id": v1.id, "to_vessel_id": v2.id, "flow_function_name": None, "color": "#00ff00", "width": 3},
        ]}
        db.session.commit()
        layout = DashboardLayout(name="L Snapshot Pipes", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    conns = resp.get_json()["connections"]
    assert conns[0]["color"] == "#00ff00"
    assert conns[0]["width"] == 3


def test_view_renderiza_svg_do_vasilhame(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L SVG")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", label_text="Caldeira")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "db-vessel-svg" in html
    assert "db-vessel-fill-rect" in html
    assert "dbEditToggle" in html  # botão de modo edição presente


def test_script_da_dashboard_vem_depois_do_bootstrap_bundle(app, client):
    """
    Achado real (conversa): o <script> da dashboard estava dentro de
    {% block content %} (renderiza ANTES do bootstrap.bundle.min.js
    carregar), então `new bootstrap.Modal(...)` estourava
    ReferenceError e travava o resto do script — os botões de
    Configurações/Adicionar Widget/Editar Tubulação simplesmente nunca
    tinham o listener registrado. Corrigido movendo pra
    {% block extra_js %} (depois do bootstrap, igual toda outra tela).
    Este teste garante que isso nunca regride silenciosamente.
    """
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Ordem Script")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    bootstrap_pos = html.find("bootstrap.bundle.min.js")
    dashboard_script_pos = html.find("dbEditToggle")  # dentro do <script> da dashboard
    assert bootstrap_pos != -1, "bootstrap.bundle.min.js não encontrado na página"
    assert dashboard_script_pos != -1
    # o botão em si (HTML) pode vir antes; o que importa é o <script> em si
    script_tag_pos = html.rfind("<script>", 0, html.find("(function () {"))
    assert script_tag_pos > bootstrap_pos, (
        "O <script> da dashboard está renderizando ANTES do bootstrap.bundle.min.js — "
        "vai quebrar new bootstrap.Modal(...) de novo."
    )


def test_config_manual_control_enabled_e_persistido(app, client):
    """Controle de acionamento manual (CraftBeerPi4 — permitir/bloquear
    clique manual num atuador, útil quando a automação já controla)."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Manual Control")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", label_text="Bomba")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={
        "config_json": {"manual_control_enabled": False},
    })
    assert resp.status_code == 200

    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.config_json["manual_control_enabled"] is False


def test_view_renderiza_checkbox_de_acionamento_manual_no_painel(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Painel Manual")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "dbPanelManualControl" in html
    assert "manual_control_enabled" in html


def test_editor_tubulacao_atuador_de_fluxo_agora_e_select_com_functions(app, client):
    """Achado real (conversa): o campo "Atuador de fluxo" era texto
    livre — vira select com as Functions de atuador disponíveis
    (mesma referência fraca cross-Addon de sempre, skill 02)."""
    _login_admin(app, client)
    with app.app_context():
        _criar_actor(name="bomba_transfer2_actor", function_name="bomba_transfer2",
                      category="actuator", actor_type="actuator")
        plant = BrewPlant(name="Planta Select Atuador")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="L Select Atuador", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "actuatorFunctionOptions" in html
    assert "bomba_transfer2" in html
    assert "db-pipe-function" in html


def test_view_tem_link_direto_pra_importar_receita(app, client):
    """Achado real (conversa): tela nova ficava 4 níveis fundo no menu
    (BrewStation > Controle de Mostura > Receitas > ...) — difícil de
    achar. Link direto adicionado no topo do Dashboard."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Link Receita")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "/brewstation/recipe-timeline/" in html
    assert "Importar Receita para Brassar" in html


def test_view_mostra_aviso_quando_layout_sem_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Sem Planta Aviso")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "ainda não tem uma" in html
    assert "Planta" in html


def test_view_nao_mostra_aviso_quando_layout_tem_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Com Aviso Off")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="L Com Planta", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "ainda não tem uma" not in html
    assert "dbEditPipesBtn" in html  # botão de tubulação aparece com planta


# ── Timeline de alertas (fired + upcoming) — achado real relatado ───────────

def test_snapshot_mostra_alertas_agendados_de_sessao_draft(app, client):
    """Achado real: 'ao importar sessão de receita ainda não apareceu
    nos alertas' — sessão gerada como rascunho (sem started_at) nunca
    tinha NADA no widget, porque só mostrava BrewSessionAlarm (já
    disparado). Agora mostra a timeline agendada mesmo em rascunho."""
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Draft Alertas")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(name="S Draft Alertas", plant_id=plant.id, status="draft")  # sem started_at
        db.session.add(session)
        db.session.commit()
        db.session.add(BrewSessionStep(
            session_id=session.id, step_index=0, name="Lúpulo Amargor", step_type="alert",
            trigger_at_seconds=3000, alarm_fired=False,
        ))
        db.session.commit()
        layout = DashboardLayout(name="L Draft Alertas", plant_id=plant.id)
        widget = DashboardWidget(layout_id=None, widget_type="alarm_list")
        db.session.add(layout)
        db.session.commit()
        widget.layout_id = layout.id
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    widget_data = list(data["widgets"].values())[0]
    assert len(widget_data["upcoming"]) == 1
    assert widget_data["upcoming"][0]["name"] == "Lúpulo Amargor"
    assert widget_data["upcoming"][0]["seconds_until"] is None  # rascunho, sem relógio rodando
    assert widget_data["session_status"] == "draft"


def test_snapshot_mostra_contagem_regressiva_em_sessao_ativa(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Ativa Alertas")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(
            name="S Ativa Alertas", plant_id=plant.id, status="active",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=600),
        )
        db.session.add(session)
        db.session.commit()
        db.session.add(BrewSessionStep(
            session_id=session.id, step_index=0, name="Lúpulo Aroma", step_type="alert",
            trigger_at_seconds=900, alarm_fired=False,  # 300s no futuro
        ))
        db.session.commit()
        layout = DashboardLayout(name="L Ativa Alertas", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="alarm_list")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    widget_data = list(data["widgets"].values())[0]
    assert len(widget_data["upcoming"]) == 1
    assert 250 < widget_data["upcoming"][0]["seconds_until"] < 310  # ~300s restantes


def test_snapshot_alerta_ja_disparado_nao_aparece_em_upcoming(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Ja Disparado")
        db.session.add(plant)
        db.session.commit()
        session = BrewSession(
            name="S Ja Disparado", plant_id=plant.id, status="active",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=1000),
        )
        db.session.add(session)
        db.session.commit()
        db.session.add(BrewSessionStep(
            session_id=session.id, step_index=0, name="Já disparado", step_type="alert",
            trigger_at_seconds=500, alarm_fired=True,
        ))
        db.session.add(BrewSessionAlarm(session_id=session.id, message="Já disparado", severity="medium"))
        db.session.commit()
        layout = DashboardLayout(name="L Ja Disparado", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="alarm_list")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    widget_data = list(data["widgets"].values())[0]
    assert widget_data["upcoming"] == []
    assert len(widget_data["fired"]) == 1


def test_snapshot_sem_nenhuma_sessao_devolve_listas_vazias(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Sem Sessao Nenhuma")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="L Sem Sessao Nenhuma", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="alarm_list")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    widget_data = list(data["widgets"].values())[0]
    assert widget_data == {"fired": [], "upcoming": []}


def test_view_html_renderiza_upcoming_no_js(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L JS Upcoming")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="alarm_list")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "data.upcoming" in html
    assert "data.fired" in html


# ── step_card no snapshot do Dashboard (conversa — Ponto 2) ──────────────────

def test_create_widget_step_card_via_editor(app):
    with app.app_context():
        layout = DashboardLayout(name="L Step Card")
        db.session.add(layout)
        db.session.commit()
        widget = svc.create_widget_from_editor(layout, widget_type="step_card", label_text="Etapa", x=40, y=40)
        assert widget.widget_type == "step_card"
        assert widget.vessel_id is None
        assert widget.device_function_name is None


def test_snapshot_step_card_sem_sessao_ativa(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Step Card Vazia")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="L Step Card Vazia", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="step_card")
        db.session.add(widget)
        db.session.commit()
        layout_id, widget_id = layout.id, widget.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    assert data["active_recipe_id"] is None
    assert data["widgets"][str(widget_id)] == {"current": None, "next": None}


def test_snapshot_step_card_com_sessao_ativa_mostra_etapa_atual(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Snapshot Card")
        db.session.add(recipe)
        db.session.commit()
        mash = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash", temperatura=66, tempo_min=30)
        db.session.add(mash)
        db.session.commit()

        plant = BrewPlant(name="Planta Step Card Ativa")
        db.session.add(plant)
        db.session.commit()

        session = rt_svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="S", status="active")

        layout = DashboardLayout(name="L Step Card Ativa", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="step_card")
        db.session.add(widget)
        db.session.commit()
        layout_id, widget_id, recipe_id = layout.id, widget.id, recipe.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    assert data["active_recipe_id"] == recipe_id
    assert data["widgets"][str(widget_id)]["current"]["name"] == "Mash"


# ── Paleta arrastável + painel lateral (Ponto 3) ─────────────────────────────

def test_create_widget_tipo_text_via_editor(app):
    with app.app_context():
        layout = DashboardLayout(name="L Text Widget")
        db.session.add(layout)
        db.session.commit()
        widget = svc.create_widget_from_editor(layout, widget_type="text", label_text="", x=10, y=10)
        assert widget.widget_type == "text"
        assert widget.vessel_id is None
        assert widget.device_function_name is None


def test_create_widget_tipo_image_via_editor(app):
    with app.app_context():
        layout = DashboardLayout(name="L Image Widget")
        db.session.add(layout)
        db.session.commit()
        widget = svc.create_widget_from_editor(layout, widget_type="image", label_text="", x=10, y=10)
        assert widget.widget_type == "image"


def test_update_widget_config_vincula_vessel_id_pela_primeira_vez(app):
    """Achado da conversa (Ponto 3): widget nasce solto da paleta —
    o painel lateral agora PODE setar vessel_id/device_function_name,
    diferente da restrição antiga do modal."""
    with app.app_context():
        layout = DashboardLayout(name="L Vincula Vessel")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        assert widget.vessel_id is None

        svc.update_widget_config(widget, vessel_id=7)
        assert widget.vessel_id == 7


def test_update_widget_config_vincula_device_function_name(app):
    with app.app_context():
        layout = DashboardLayout(name="L Vincula Function")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle")
        db.session.add(widget)
        db.session.commit()

        svc.update_widget_config(widget, device_function_name="bomba_transfer")
        assert widget.device_function_name == "bomba_transfer"


def test_update_widget_config_clear_reference_limpa_vinculo(app):
    with app.app_context():
        layout = DashboardLayout(name="L Clear Ref")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=3)
        db.session.add(widget)
        db.session.commit()

        svc.update_widget_config(widget, clear_reference=True)
        assert widget.vessel_id is None
        assert widget.device_function_name is None


def test_update_config_rota_web_aceita_vessel_id(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Rota Vincula")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={"vessel_id": 9})
    assert resp.status_code == 200
    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.vessel_id == 9


def test_view_renderiza_badge_nao_configurado_pra_widget_solto(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Badge Nao Config")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle")  # sem device_function_name
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "Não configurado" in html


def test_view_nao_renderiza_badge_pra_widget_ja_vinculado(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Badge Configurado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", device_function_name="bomba_x")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "Não configurado" not in html


def test_view_renderiza_paleta_com_os_9_tipos(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Paleta")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    for wtype in ["digital", "gauge", "chart", "toggle", "vessel", "step_card", "alarm_list", "text", "image"]:
        assert f'data-widget-type="{wtype}"' in html


def test_view_renderiza_widget_text_e_image(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Text Image Render")
        db.session.add(layout)
        db.session.commit()
        text_w = DashboardWidget(layout_id=layout.id, widget_type="text", config_json={"content": "Aviso importante"})
        image_w = DashboardWidget(layout_id=layout.id, widget_type="image")
        db.session.add_all([text_w, image_w])
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "Aviso importante" in html
    assert "Sem imagem" in html


def test_view_nao_referencia_modal_removido(app, client):
    """Garante que o modal de Configurações/Adicionar Widget antigos
    foram mesmo removidos, não só escondidos (conversa — Ponto 3)."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Sem Modal Antigo")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'id="dbAddWidgetModal"' not in html
    assert 'id="dbConfigModal"' not in html
    assert 'id="dbSidePanel"' in html
    assert 'id="dbPalette"' in html


# ── Ajustes reportados em uso (sessão ativa, botão travado, ícone,
# Tanque, texto/imagem) ──────────────────────────────────────────────────

def test_get_active_session_pega_a_mais_recente_quando_ha_duas_active(app):
    """Achado real: .first() sem ORDER BY podia devolver a sessão active
    ANTIGA em vez da nova — sessão nova "não aparecia" no Dashboard."""
    with app.app_context():
        plant = BrewPlant(name="Planta Duas Active")
        db.session.add(plant)
        db.session.commit()
        antiga = BrewSession(name="Antiga", plant_id=plant.id, status="active")
        db.session.add(antiga)
        db.session.commit()
        nova = BrewSession(name="Nova", plant_id=plant.id, status="active")
        db.session.add(nova)
        db.session.commit()

        resolved = svc._get_active_session_for_plant(plant.id)
        assert resolved.id == nova.id


def test_snapshot_expoe_available_sessions_ordenadas_por_recente(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Available Sessions")
        db.session.add(plant)
        db.session.commit()
        s1 = BrewSession(name="S1", plant_id=plant.id, status="completed")
        db.session.add(s1)
        db.session.commit()
        s2 = BrewSession(name="S2", plant_id=plant.id, status="active")
        db.session.add(s2)
        db.session.commit()
        layout = DashboardLayout(name="L Available Sessions", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id, s1_id, s2_id = layout.id, s1.id, s2.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    ids = [s["id"] for s in data["available_sessions"]]
    assert ids[0] == s2_id  # mais recente primeiro
    assert s1_id in ids


def test_snapshot_session_id_override_forca_sessao_especifica(app, client):
    """Seletor manual de sessão (conversa): passar ?session_id= força
    aquela sessão, mesmo que não seja a "active" auto-detectada."""
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Override")
        db.session.add(recipe)
        db.session.commit()
        step = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash Override", temperatura=66, tempo_min=30)
        db.session.add(step)
        db.session.commit()

        plant = BrewPlant(name="Planta Override")
        db.session.add(plant)
        db.session.commit()

        active_session = rt_svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Active", status="active")
        draft_session = rt_svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Draft", status="draft")

        layout = DashboardLayout(name="L Override", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="step_card")
        db.session.add(widget)
        db.session.commit()
        layout_id, widget_id, draft_id = layout.id, widget.id, draft_session.id

    # Sem override: usa a "active" automática.
    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    assert resp.get_json()["active_session_id"] != draft_id

    # Com override: força a draft, mesmo ela não sendo "active".
    resp2 = client.get(f"/brewstation/dashboards/{layout_id}/snapshot?session_id={draft_id}")
    assert resp2.get_json()["active_session_id"] == draft_id


def test_snapshot_session_id_override_de_outra_planta_e_ignorado(app, client):
    """Override não pode "vazar" sessão de outra Planta pro Dashboard."""
    _login_admin(app, client)
    with app.app_context():
        plant_a = BrewPlant(name="Planta A Override")
        plant_b = BrewPlant(name="Planta B Override")
        db.session.add_all([plant_a, plant_b])
        db.session.commit()
        session_b = BrewSession(name="Sessão da Planta B", plant_id=plant_b.id, status="active")
        db.session.add(session_b)
        db.session.commit()
        layout = DashboardLayout(name="L Override Cross Plant", plant_id=plant_a.id)
        db.session.add(layout)
        db.session.commit()
        layout_id, session_b_id = layout.id, session_b.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot?session_id={session_b_id}")
    assert resp.get_json()["active_session_id"] != session_b_id


def test_view_botoes_utilitarios_do_step_card_tem_classe_no_drag(app, client):
    """Achado real: botão configurado ficava impossível de selecionar/
    arrastar porque o mousedown excluía QUALQUER <button>. Corrigido pra
    excluir só os utilitários (classe db-no-drag), não o widget Botão."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L No Drag")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="step_card")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "db-steps-manage-btn db-no-drag" in html
    assert "db-step-back-btn db-no-drag" in html
    assert "db-step-advance-btn db-no-drag" in html


def test_view_renderiza_seletor_de_icone_do_botao_com_12_opcoes(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Icon Picker")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert html.count('data-icon="') == 12
    for icon in ["bi-power", "bi-fire", "bi-droplet-fill", "bi-snow", "bi-cup-hot-fill"]:
        assert f'data-icon="{icon}"' in html


def test_toggle_widget_usa_icone_configurado(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Icone Configurado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", config_json={"icon": "bi-fire"})
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert '<i class="bi bi-fire fs-4">' in html


def test_text_widget_aplica_negrito_italico_fonte(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Texto Estilizado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(
            layout_id=layout.id, widget_type="text",
            config_json={"content": "Aviso", "bold": True, "italic": True, "font_family": "Georgia, serif", "color": "#ff0000", "font_size": 24},
        )
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "font-weight:bold" in html
    assert "font-style:italic" in html
    assert "font-family:Georgia, serif" in html
    assert "color:#ff0000" in html
    assert "font-size:24px" in html


def test_view_renderiza_seletor_de_sessao_quando_layout_tem_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant = BrewPlant(name="Planta Seletor Sessao")
        db.session.add(plant)
        db.session.commit()
        layout = DashboardLayout(name="L Com Planta", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'id="dbSessionSelector"' in html


def test_view_nao_renderiza_seletor_de_sessao_sem_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Sem Planta Seletor")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'id="dbSessionSelector"' not in html


def test_view_usa_tanque_em_vez_de_vasilhame(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Label")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "Vasilhame" not in html
    assert "Tanque" in html


# ── Upload de imagem (widget Imagem) ────────────────────────────────────────

def test_upload_image_salva_arquivo_e_devolve_url(app, client):
    import io
    _login_admin(app, client)
    data = {"image": (io.BytesIO(b"fake-png-bytes"), "logo.png")}
    resp = client.post("/brewstation/dashboards/upload-image", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "/brewstation/dashboards/imgs/" in body["url"]
    assert body["url"].endswith(".png")

    # o arquivo servido de volta deve funcionar
    resp2 = client.get(body["url"])
    assert resp2.status_code == 200
    assert resp2.data == b"fake-png-bytes"


def test_upload_image_rejeita_extensao_nao_permitida(app, client):
    import io
    _login_admin(app, client)
    data = {"image": (io.BytesIO(b"fake"), "malware.exe")}
    resp = client.post("/brewstation/dashboards/upload-image", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_upload_image_sem_arquivo_falha(app, client):
    _login_admin(app, client)
    resp = client.post("/brewstation/dashboards/upload-image", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_view_js_esconde_atuador_do_tanque_quando_manual_desligado(app, client):
    """Achado da conversa: com acionamento manual desligado, o atuador
    não deve mais aparecer (nem travado com cadeado) no widget Tanque —
    o usuário controla ele por um widget Botão separado."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Sem Manual")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "if (isActuator && !manualEnabled) return;" in html
    assert "lockSuffix" not in html


# ── Redesenho do card de Tanque (conversa — inspiração visual) ──────────────

def test_view_renderiza_card_de_tanque_redesenhado(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Redesenhado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'class="db-vessel-card' in html
    assert "db-vessel-label" in html
    assert "db-vessel-readout" in html
    assert "db-vessel-setpoint" in html


def test_view_tanque_tem_gradientes_por_faixa_de_temperatura(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Gradiente")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        layout_id, widget_id = layout.id, widget.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert f"db-fill-cold-{widget_id}" in html
    assert f"db-fill-warm-{widget_id}" in html
    assert f"db-fill-hot-{widget_id}" in html
    assert "fillGradientUrlForTemp" in html


def test_view_tanque_sem_setpoint_mostra_travessao(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Sem Setpoint")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert '<span class="db-vessel-setpoint-value">—</span>' in html


def test_view_tanque_com_setpoint_configurado_mostra_valor(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Tanque Com Setpoint")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", config_json={"setpoint": 65.5})
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert '<span class="db-vessel-setpoint-value">65.5°C</span>' in html


def test_view_painel_lateral_tem_campo_setpoint_pro_tanque(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Painel Setpoint")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'id="dbPanelSetpoint"' in html
    assert "'setpoint'" in html  # presente em panelFieldsByType.vessel


def test_update_config_salva_setpoint(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Salva Setpoint")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/config", json={"config_json": {"setpoint": 68}})
    assert resp.status_code == 200
    with app.app_context():
        widget = DashboardWidget.query.get(widget_id)
        assert widget.config_json["setpoint"] == 68


# ── Barra de topo unificada (conversa — referência visual) ──────────────────

def test_snapshot_sem_sessao_ativa_header_e_none(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Header Sem Sessao")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    assert data["header"] is None


def test_snapshot_com_sessao_ativa_popula_header(app, client):
    _login_admin(app, client)
    with app.app_context():
        recipe = MashRecipe(name="Receita Header Bar")
        db.session.add(recipe)
        db.session.commit()
        step = RecipeStep(recipe_id=recipe.id, step_type="mash", ordem=0, nome="Mash Header", temperatura=66, tempo_min=30)
        db.session.add(step)
        db.session.commit()

        plant = BrewPlant(name="Planta Header Bar")
        db.session.add(plant)
        db.session.commit()

        session = rt_svc.generate_session_from_recipe(recipe.id, plant_id=plant.id, name="Sessão Header Bar", status="active")

        layout = DashboardLayout(name="L Header Com Sessao", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/snapshot")
    data = resp.get_json()
    assert data["header"] is not None
    assert data["header"]["recipe_name"] == "Receita Header Bar"
    assert data["header"]["session_status"] == "active"
    assert data["header"]["current_step"] is not None
    assert data["header"]["current_step"]["name"] == "Mash Header"


def test_view_renderiza_barra_de_topo(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Barra Topo HTML")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'id="dbHeaderBar"' in html
    assert 'id="dbHeaderRecipeName"' in html
    assert 'id="dbHeaderStepName"' in html
    assert 'id="dbHeaderTimerValue"' in html
    assert 'id="dbHeaderPauseBtn"' in html
    assert 'id="dbHeaderStopBtn"' in html


def test_toggle_pause_session_active_para_paused(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Pausar", status="active")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/toggle-pause")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "paused"
    with app.app_context():
        assert BrewSession.query.get(session_id).status == "paused"


def test_toggle_pause_session_paused_para_active(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Retomar", status="paused")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/toggle-pause")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "active"


def test_toggle_pause_session_draft_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Draft Pausar", status="draft")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/toggle-pause")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_stop_session_marca_completed(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Parar", status="active")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/stop")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    with app.app_context():
        assert BrewSession.query.get(session_id).status == "completed"


def test_stop_session_ja_completed_falha(app, client):
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessão Ja Completa", status="completed")
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    resp = client.post(f"/brewstation/dashboards/sessions/{session_id}/stop")
    assert resp.status_code == 400


def test_pause_stop_sessao_inexistente_404(app, client):
    _login_admin(app, client)
    resp1 = client.post("/brewstation/dashboards/sessions/999999/toggle-pause")
    assert resp1.status_code == 404
    resp2 = client.post("/brewstation/dashboards/sessions/999999/stop")
    assert resp2.status_code == 404


# ── Alarmes com borda por severidade (terceira peça da referência visual) ──

def test_view_renderiza_card_de_alarmes_redesenhado(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Alarmes Redesenhado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="alarm_list")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert 'class="db-alarm-card' in html
    assert "db-alarm-header" in html
    assert 'class="db-alarm-list' in html


def test_view_js_alarmes_usa_textcontent_pra_mensagem(app, client):
    """Achado da conversa: mensagem/nome do alarme são dado externo —
    trocado de innerHTML (risco de XSS) pra textContent."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Alarmes TextContent")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "msg.textContent = a.message" in html
    assert "msg.textContent = u.name" in html


def test_view_js_alarmes_tem_classes_de_severidade(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Alarmes Severidade CSS")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    for cls in ["db-alarm-sev-critical", "db-alarm-sev-high", "db-alarm-sev-medium", "db-alarm-sev-low", "db-alarm-sev-upcoming"]:
        assert cls in html


# ── Achado real: pausar não congelava o tempo da etapa (bug reportado) ──────

def test_view_step_card_tem_badge_pausado_no_html(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Badge Pausado")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="step_card")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "db-step-paused-badge" in html
    assert "data.session_status !== 'paused'" in html


def test_toggle_pause_session_via_rota_congela_o_timer_ao_retomar(app, client):
    """Teste de ponta a ponta via HTTP: pausa, avança o relógio
    artificialmente (fixando paused_at no passado), retoma pela rota,
    e confirma que started_at foi deslocado — não é só a unidade do
    service, é a rota real que o botão da barra de topo chama."""
    _login_admin(app, client)
    with app.app_context():
        session = BrewSession(name="Sessao Rota Pausa", status="active",
                               started_at=datetime.now(timezone.utc) - timedelta(hours=1))
        db.session.add(session)
        db.session.commit()
        session_id = session.id
        original_started_at = session.started_at
        if original_started_at.tzinfo is None:
            original_started_at = original_started_at.replace(tzinfo=timezone.utc)

    resp1 = client.post(f"/brewstation/dashboards/sessions/{session_id}/toggle-pause")
    assert resp1.get_json()["status"] == "paused"

    with app.app_context():
        session = BrewSession.query.get(session_id)
        session.paused_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.session.commit()

    resp2 = client.post(f"/brewstation/dashboards/sessions/{session_id}/toggle-pause")
    assert resp2.get_json()["status"] == "active"

    with app.app_context():
        session = BrewSession.query.get(session_id)
        new_started_at = session.started_at
        if new_started_at.tzinfo is None:
            new_started_at = new_started_at.replace(tzinfo=timezone.utc)
        delta_minutes = (new_started_at - original_started_at).total_seconds() / 60
        assert 4.5 <= delta_minutes <= 5.5


# ── Achado real (conversa): botão Botão não acionava + sem aviso de MQTT ──

def test_view_click_le_widgetid_do_wrapper_nao_do_botao(app, client):
    """Achado real: o clique lia widgetId/config direto do <button>
    .db-toggle, que não tem esses atributos (ficam no wrapper
    .db-widget) — o comando ia com id "undefined" e nunca acionava
    nada de verdade."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Click Wrapper")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "const widgetEl = toggleBtn.closest('.db-widget');" in html
    assert "lastSnapshot.widgets[widgetEl.dataset.widgetId]" in html
    assert "maybeConfirmAndSetValue(widgetEl, !currentValue, null);" in html


def test_view_renderwidget_aplica_estado_no_botao_nao_no_wrapper(app, client):
    """Achado real: renderWidget aplicava btn-success/disabled no
    wrapper .db-widget (um <div>), nunca no <button> de verdade — o
    botão nunca mudava de cor nem ficava desabilitado de verdade."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L RenderWidget Botao")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "const toggleEl = el.querySelector('.db-toggle') || el;" in html
    assert "toggleEl.classList.toggle('btn-success', !!state);" in html
    assert "toggleEl.disabled = !manualEnabled;" in html


def test_view_postsetvalue_avisa_quando_mqtt_desconectado(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Aviso MQTT")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "data.mqtt_connected === false" in html
    assert "broker MQTT não está conectado" in html


def test_set_widget_value_expoe_mqtt_connected_false_sem_broker(app):
    """Sem broker rodando nos testes, mqtt_connected sempre vem False —
    o cache local ainda é atualizado (comportamento já existente), mas
    agora o chamador sabe que não publicou de verdade."""
    with app.app_context():
        _criar_actor(name="mqtt_status_actor", function_name="mqtt_status_fn", category="actuator", actor_type="actuator")
        layout = DashboardLayout(name="L MQTT Status")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", device_function_name="mqtt_status_fn")
        db.session.add(widget)
        db.session.commit()

        result = svc.set_widget_value(widget, True)
        assert result["ok"] is True
        assert result["mqtt_connected"] is False


def test_set_value_rota_web_expoe_mqtt_connected(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_actor(name="mqtt_rota_actor", function_name="mqtt_rota_fn", category="actuator", actor_type="actuator")
        layout = DashboardLayout(name="L MQTT Rota")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle", device_function_name="mqtt_rota_fn")
        db.session.add(widget)
        db.session.commit()
        widget_id = widget.id

    resp = client.post(f"/brewstation/dashboards/widgets/{widget_id}/set-value", json={"value": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "mqtt_connected" in data
    assert data["mqtt_connected"] is False


def test_set_widget_value_sem_function_devolve_erro_descritivo(app):
    with app.app_context():
        layout = DashboardLayout(name="L Sem Function")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="toggle")
        db.session.add(widget)
        db.session.commit()

        result = svc.set_widget_value(widget, True)
        assert result["ok"] is False
        assert result["error"]
        assert result["mqtt_connected"] is None


# ── Auditoria de acionamento (BrewSessionLog source="user") — conversa ──────

def test_set_widget_value_grava_auditoria_com_sessao_ativa(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_audit")
        _criar_actor(name="resistencia_audit_actor", function_name="resistencia_audit", category="actuator", actor_type="actuator")
        session = BrewSession(name="Sessão Auditoria", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        layout = DashboardLayout(name="L Audit", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id)
        db.session.add(widget)
        db.session.commit()

        result = svc.set_widget_value(widget, True, role_key="actor_heat")
        assert result["ok"] is True

        logs = BrewSessionLog.query.filter_by(session_id=session.id, source="user").all()
        assert len(logs) == 1
        assert logs[0].detail_json["function_name"] == "resistencia_audit"
        assert logs[0].detail_json["value"] is True


def test_set_widget_value_nao_grava_auditoria_sem_sessao_ativa(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_sem_sessao")
        _criar_actor(name="resistencia_sem_sessao_actor", function_name="resistencia_sem_sessao", category="actuator", actor_type="actuator")

        layout = DashboardLayout(name="L Sem Sessao", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="vessel", vessel_id=vessel.id)
        db.session.add(widget)
        db.session.commit()

        result = svc.set_widget_value(widget, True, role_key="actor_heat")
        assert result["ok"] is True
        # sem sessão ativa pra planta -> não existe onde anexar o log (session_id NOT NULL)
        assert BrewSessionLog.query.filter_by(source="user").count() == 0


# ── Painel de status (widget device_status) — conversa ──────────────────────

def test_get_plant_device_status_lista_todos_os_mappings(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="sensor_temp", function_name="mash_temp_status")
        _criar_actor(name="mash_temp_status_sensor", function_name="mash_temp_status", category="sensor", actor_type="sensor")
        second_mapping = BrewPlantMapping(vessel_id=vessel.id, role_key="actor_heat", device_function_name="heater_status")
        db.session.add(second_mapping)
        db.session.commit()
        _criar_actor(name="heater_status_actor", function_name="heater_status", category="actuator", actor_type="actuator")
        device_service.set_value("heater_status_actor", True)

        status = svc.get_plant_device_status(plant.id)
        assert len(status) == 2
        by_role = {item["role_key"]: item for item in status}
        assert by_role["actor_heat"]["value"] is True
        assert by_role["actor_heat"]["vessel_name"] == vessel.label_text
        assert "is_risk" in by_role["sensor_temp"]


def test_set_mapping_value_aciona_e_audita(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_mapping")
        _criar_actor(name="resistencia_mapping_actor", function_name="resistencia_mapping", category="actuator", actor_type="actuator")
        session = BrewSession(name="Sessão Mapping", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        result = svc.set_mapping_value(mapping.id, True)
        assert result["ok"] is True
        assert device_service.get_value("resistencia_mapping_actor") is True
        assert BrewSessionLog.query.filter_by(session_id=session.id, source="user").count() == 1


def test_set_mapping_value_mapping_inexistente_falha(app):
    with app.app_context():
        result = svc.set_mapping_value(99999, True)
        assert result["ok"] is False
        assert result["error"]


# ── Log de comunicação (widget comm_log) — conversa ──────────────────────────

def test_get_communication_log_combina_acoes_e_mqtt_raw(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_log")
        _criar_actor(name="resistencia_log_actor", function_name="resistencia_log", category="actuator", actor_type="actuator")
        session = BrewSession(name="Sessão Log", plant_id=plant.id, status="active")
        db.session.add(session)
        db.session.commit()

        svc.set_mapping_value(mapping.id, True)

        result = svc.get_communication_log(plant.id)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["source"] == "user"
        # sem broker MQTT real no teste, o arquivo de integração pode nem
        # existir ainda — só garante que a chave sempre vem como lista
        assert isinstance(result["mqtt_raw"], list)


def test_get_communication_log_planta_sem_sessao_devolve_actions_vazio(app):
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_log2")
        result = svc.get_communication_log(plant.id)
        assert result["actions"] == []


# ── Renderização real da view (front-end) — conversa ─────────────────────────

def test_view_renderiza_widget_device_status_e_comm_log(app, client):
    """Achado real (conversa): o único jeito confiável de pegar erro de
    Jinja/url_for nos dois widgets novos é renderizando a view de
    verdade — parse Jinja isolado não pega url_for quebrado nem
    variável indefinida em runtime."""
    _login_admin(app, client)
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_view")
        layout = DashboardLayout(name="L Status Widgets", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        w1 = DashboardWidget(layout_id=layout.id, widget_type="device_status", label_text="Status")
        w2 = DashboardWidget(layout_id=layout.id, widget_type="comm_log", label_text="Log")
        db.session.add_all([w1, w2])
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "db-status-card" in html
    assert "db-collapse-toggle" in html
    assert "db-comm-tabs" in html
    assert "deviceStatusUrl" in html
    assert "commLogUrl" in html


def test_view_renderiza_device_status_sem_planta_no_layout(app, client):
    """widget_type novo é aceito mesmo em layout sem Planta (skill: tipo
    não exige vessel_id/device_function_name) — só mostra o aviso
    inline em vez de tentar buscar dado que não existe."""
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Sem Planta")
        db.session.add(layout)
        db.session.commit()
        widget = DashboardWidget(layout_id=layout.id, widget_type="device_status", label_text="Status")
        db.session.add(widget)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "não tem Planta associada" in html


# ── Rotas web novas (device-status / mapping set-value / comm-log) ──────────

def test_rota_web_plant_device_status(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="sensor_temp", function_name="temp_rota_status")
        _criar_actor(name="temp_rota_status_sensor", function_name="temp_rota_status")
        plant_id = plant.id

    resp = client.get(f"/brewstation/dashboards/plants/{plant_id}/device-status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["role_key"] == "sensor_temp"


def test_rota_web_mapping_set_value(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_rota")
        _criar_actor(name="resistencia_rota_actor", function_name="resistencia_rota", category="actuator", actor_type="actuator")
        mapping_id = mapping.id

    resp = client.post(f"/brewstation/dashboards/mappings/{mapping_id}/set-value", json={"value": True})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_rota_web_plant_comm_log(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant, vessel, mapping = _criar_plant_vessel_mapping(role_key="actor_heat", function_name="resistencia_rota_log")
        plant_id = plant.id

    resp = client.get(f"/brewstation/dashboards/plants/{plant_id}/comm-log")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "actions" in data
    assert "mqtt_raw" in data
