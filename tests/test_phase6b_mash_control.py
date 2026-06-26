"""
tests/test_phase6b_mash_control.py

Cobre feature_mash_control (escopo CRUD, sem motor de controle em
tempo real — decisão registrada no BACKLOG.md): 12 tabelas com
prefixo correto, referência fraca (sem FK) mash_control ->
device_manager (skill 02 — atualizado para a promoção de
feature_device_manager a Addon independente, ver
docs/skills/05-proposta-addon-device-manager-e-mqtt.md), cadeia de FK
interna (plant -> vessel -> mapping, recipe -> session -> step).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        admin = User(
            username="admin", email="admin@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


def test_12_tabelas_de_mash_control_existem_com_prefixo_correto(app):
    esperado = {
        "tesseract_brewstation_mashctrl_recipe",
        "tesseract_brewstation_mashctrl_plant",
        "tesseract_brewstation_mashctrl_plant_vessel",
        "tesseract_brewstation_mashctrl_plant_mapping",
        "tesseract_brewstation_mashctrl_session",
        "tesseract_brewstation_mashctrl_session_step",
        "tesseract_brewstation_mashctrl_session_log",
        "tesseract_brewstation_mashctrl_session_alarm",
        "tesseract_brewstation_mashctrl_layout",
        "tesseract_brewstation_mashctrl_widget",
        "tesseract_brewstation_mashctrl_rule",
        "tesseract_brewstation_mashctrl_rule_log",
    }
    with app.app_context():
        assert esperado.issubset(set(db.metadata.tables.keys()))


def test_referencia_fraca_mash_control_para_device_manager(app, client):
    """
    BrewPlantMapping.device_function_name referencia DeviceFunction por
    nome (referência fraca) — NUNCA FK direta entre Addons (skill 02).
    Atualizado para a promoção de feature_device_manager a Addon
    independente (docs/skills/05-proposta-addon-device-manager-e-mqtt.md).
    """
    _login_admin(app, client)

    r = client.post(
        "/api/device-manager/device-functions/",
        json={"name": "temp_fk_test", "display_name": "Temp", "category": "sensor"},
    )
    function_name = r.get_json()["item"]["name"]

    r = client.post("/api/brewstation/brew-plants/", json={"name": "Planta FK"})
    plant_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/brew-plant-vessels/",
        json={"plant_id": plant_id, "vessel_type": "mash_tun", "label_text": "Panela FK"},
    )
    vessel_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/brew-plant-mappings/",
        json={"vessel_id": vessel_id, "role_key": "sensor_temp", "device_function_name": function_name},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["device_function_name"] == function_name


def test_cadeia_recipe_session_step_via_http(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/mash-recipes/", json={"name": "IPA Teste"})
    recipe_id = r.get_json()["item"]["id"]

    r = client.post("/api/brewstation/brew-plants/", json={"name": "Planta Sessao"})
    plant_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/brew-sessions/",
        json={"name": "Sessao Teste", "plant_id": plant_id, "recipe_id": recipe_id},
    )
    assert r.status_code == 201
    session_id = r.get_json()["item"]["id"]
    assert r.get_json()["item"]["status"] == "draft"

    r = client.post(
        "/api/brewstation/brew-session-steps/",
        json={"session_id": session_id, "step_index": 0, "name": "Mostura"},
    )
    assert r.status_code == 201

    r = client.post(
        "/api/brewstation/brew-session-logs/",
        json={"session_id": session_id, "message": "Sessão iniciada"},
    )
    assert r.status_code == 201

    r = client.post(
        "/api/brewstation/brew-session-alarms/",
        json={"session_id": session_id, "message": "Temperatura alta"},
    )
    assert r.status_code == 201


def test_dashboard_layout_e_widget_com_referencia_fraca_opcional(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/dashboard-layouts/", json={"name": "Layout 1"})
    layout_id = r.get_json()["item"]["id"]

    # widget sem device_function_name (opcional/nullable)
    r = client.post(
        "/api/brewstation/dashboard-widgets/",
        json={"layout_id": layout_id, "widget_type": "gauge"},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["device_function_name"] is None


def test_automation_rule_referencia_duas_functions_diferentes(app, client):
    """
    AutomationRule tem DUAS referências fracas pra DeviceFunction
    (sensor e ator), por `name` — confirma que múltiplas referências
    pro mesmo módulo externo funcionam sem FK (skill 02).
    """
    _login_admin(app, client)

    r1 = client.post(
        "/api/device-manager/device-functions/",
        json={"name": "sensor_temp_rule", "display_name": "Sensor", "category": "sensor"},
    )
    sensor_name = r1.get_json()["item"]["name"]

    r2 = client.post(
        "/api/device-manager/device-functions/",
        json={"name": "actor_heat_rule", "display_name": "Aquecedor", "category": "actuator"},
    )
    actor_name = r2.get_json()["item"]["name"]

    r = client.post(
        "/api/brewstation/automation-rules/",
        json={
            "name": "Regra Teste", "sensor_function_name": sensor_name,
            "condition_operator": "<=", "condition_value": 65.0,
            "actor_function_name": actor_name, "actor_action": "ON",
        },
    )
    assert r.status_code == 201
    item = r.get_json()["item"]
    assert item["sensor_function_name"] == sensor_name
    assert item["actor_function_name"] == actor_name


def test_permissoes_existem_para_as_12_entidades(app):
    from model.core.permission import Permission

    with app.app_context():
        nomes = {p.name for p in Permission.query.all()}
        plurals = [
            "mash_recipes", "brew_plants", "brew_plant_vessels", "brew_plant_mappings",
            "brew_sessions", "brew_session_steps", "brew_session_logs", "brew_session_alarms",
            "dashboard_layouts", "dashboard_widgets", "automation_rules", "automation_rule_logs",
        ]
        for plural in plurals:
            assert f"{plural}.create" in nomes
            assert f"{plural}.list" in nomes
