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


def test_view_renderiza_checkbox_de_acionamento_manual_no_modal(app, client):
    _login_admin(app, client)
    with app.app_context():
        layout = DashboardLayout(name="L Modal Manual")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboards/{layout_id}/view")
    html = resp.data.decode("utf-8")
    assert "dbConfigManualControl" in html
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
