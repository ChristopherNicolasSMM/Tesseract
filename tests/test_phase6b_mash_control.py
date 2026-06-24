"""
tests/test_phase6b_mash_control.py

Cobre feature_mash_control (escopo CRUD, sem motor de controle em
tempo real — decisão registrada no BACKLOG.md): 12 tabelas com
prefixo correto, FK cross-Feature confirmada (mash_control ->
device_manager, mesmo Addon — skill 02), cadeia de FK interna
(plant -> vessel -> mapping, recipe -> session -> step).
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


def test_fk_cross_feature_mash_control_para_device_manager(app, client):
    """
    BrewPlantMapping.device_function_id referencia DeviceFunction
    (Feature diferente, mesmo Addon) — skill 02, clarificação
    adicionada na Fase 6: permitido.
    """
    _login_admin(app, client)

    r = client.post(
        "/api/brewstation/device-functions/",
        json={"name": "temp_fk_test", "display_name": "Temp", "category": "sensor"},
    )
    function_id = r.get_json()["item"]["id"]

    r = client.post("/api/brewstation/brew-plants/", json={"name": "Planta FK"})
    plant_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/brew-plant-vessels/",
        json={"plant_id": plant_id, "vessel_type": "mash_tun", "label_text": "Panela FK"},
    )
    vessel_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/brew-plant-mappings/",
        json={"vessel_id": vessel_id, "role_key": "sensor_temp", "device_function_id": function_id},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["device_function_id"] == function_id


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


def test_dashboard_layout_e_widget_com_fk_cross_feature_opcional(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/dashboard-layouts/", json={"name": "Layout 1"})
    layout_id = r.get_json()["item"]["id"]

    # widget sem device_function_id (opcional/nullable)
    r = client.post(
        "/api/brewstation/dashboard-widgets/",
        json={"layout_id": layout_id, "widget_type": "gauge"},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["device_function_id"] is None


def test_automation_rule_referencia_duas_functions_diferentes(app, client):
    """
    AutomationRule tem DUAS FKs pra DeviceFunction (sensor e ator) —
    confirma que múltiplas FKs pro mesmo alvo cross-Feature funcionam.
    """
    _login_admin(app, client)

    r1 = client.post(
        "/api/brewstation/device-functions/",
        json={"name": "sensor_temp_rule", "display_name": "Sensor", "category": "sensor"},
    )
    sensor_id = r1.get_json()["item"]["id"]

    r2 = client.post(
        "/api/brewstation/device-functions/",
        json={"name": "actor_heat_rule", "display_name": "Aquecedor", "category": "actuator"},
    )
    actor_id = r2.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/automation-rules/",
        json={
            "name": "Regra Teste", "sensor_function_id": sensor_id,
            "condition_operator": "<=", "condition_value": 65.0,
            "actor_function_id": actor_id, "actor_action": "ON",
        },
    )
    assert r.status_code == 201
    item = r.get_json()["item"]
    assert item["sensor_function_id"] == sensor_id
    assert item["actor_function_id"] == actor_id


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
