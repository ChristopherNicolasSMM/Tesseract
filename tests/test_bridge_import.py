"""
tests/test_bridge_import.py

Cobre o "cadastro primário" (conversa — arquitetura de dashboard
consolidada): importação de devices.yml + recipe.yml no formato real
do tesseract-device-bridge (github.com/ChristopherNicolasSMM/Tesseract-Device-Bridge)
pra Device/Function/Actor + Planta/Vasilhame/Mapeamento + Dashboard.

Os YAMLs de teste são os arquivos reais enviados na conversa (Lager
com mostura em 2 etapas + fervura), não simplificados — cobre o caso
real de sensor 1-Wire compartilhando pino, atuador failsafe/is_risk,
e vasilhame com múltiplas bombas ao longo das etapas.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.services import bridge_import_service as svc


DEVICES_YAML = """
mqtt:
  enabled: false
  host: localhost
  port: 1883
  client_id: tesseract_bridge_01
  topic_prefix: brewery

backend: simulated

panel:
  enabled: true
  host: 0.0.0.0
  port: 8088

devices:
  - id: mash_tun_temp
    name: "Temperatura Mostura"
    role: sensor
    subtype: temperature
    unit: "°C"
    state_topic: "sensors/mash_tun_temp/state"
    hardware:
      pin: 4
      driver: ds18b20
      address: "28-0000071234ab"
    simulated:
      initial_value: 25.0
      min: 0
      max: 120

  - id: boil_temp
    name: "Temperatura Fervura"
    role: sensor
    subtype: temperature
    unit: "°C"
    state_topic: "sensors/boil_temp/state"
    hardware:
      pin: 4
      driver: ds18b20
      address: "28-0000071234cd"
    simulated:
      initial_value: 100.0
      min: 0
      max: 120

  - id: chiller_out_temp
    name: "Temperatura Saída Chiller"
    role: sensor
    subtype: temperature
    unit: "°C"
    state_topic: "sensors/chiller_out_temp/state"
    hardware:
      pin: 4
      driver: ds18b20
      address: "28-0000071234ef"
    simulated:
      initial_value: 18.0
      min: 0
      max: 100

  - id: mash_heater
    name: "Resistência Caldeira Mostura"
    role: actuator
    subtype: digital
    command_topic: "actuators/mash_heater/set"
    state_topic: "actuators/mash_heater/state"
    hardware:
      pin: 17
    failsafe_value: false
    is_risk: true
    failsafe_timeout_seconds: 30

  - id: boil_heater
    name: "Resistência Caldeira Fervura"
    role: actuator
    subtype: digital
    command_topic: "actuators/boil_heater/set"
    state_topic: "actuators/boil_heater/state"
    hardware:
      pin: 27
    failsafe_value: false
    is_risk: true
    failsafe_timeout_seconds: 30

  - id: pump_b1
    name: "Bomba B1 (Mostura)"
    role: actuator
    subtype: digital
    command_topic: "actuators/pump_b1/set"
    hardware:
      pin: 22
    failsafe_value: false
    is_risk: true
    failsafe_timeout_seconds: 30

  - id: pump_b2
    name: "Bomba B2 (Fervura + Whirlpool + Chiller)"
    role: actuator
    subtype: digital
    command_topic: "actuators/pump_b2/set"
    hardware:
      pin: 26
    failsafe_value: false
    is_risk: true
    failsafe_timeout_seconds: 30
"""

RECIPE_YAML = """
name: "Lagers da Casa"

vessels:
  - id: mash
    name: "Mash"
    order: 0
    heater_device_id: mash_heater
    sensor_device_id: mash_tun_temp
    pid:
      kp: 5.0
      ki: 0.1
      kd: 0.0
    window_seconds: 10

  - id: boil
    name: "Boil"
    order: 1
    heater_device_id: boil_heater
    sensor_device_id: boil_temp
    pid:
      kp: 4.0
      ki: 0.05
      kd: 0.0
    window_seconds: 10

steps:
  - vessel: mash
    label: "Mostura - Beta-Amilase"
    target_temp: 67
    hold_minutes: 40
    pumps: [pump_b1]

  - vessel: mash
    label: "Mostura - Alfa-Amilase"
    target_temp: 67
    hold_minutes: 20
    pumps: [pump_b1]

  - vessel: mash
    label: "Mostura - Mash Out"
    target_temp: 75
    hold_minutes: 15
    pumps: [pump_b1]

  - vessel: boil
    label: "Fervura"
    target_temp: 100
    hold_minutes: 60
    pumps: [pump_b2]
    hop_alarms:
      - minutes_remaining: 60
        label: "Lúpulo Amargor - 30g Magnum"
      - minutes_remaining: 55
        label: "Lúpulo Amargor - 10g Magnum"
      - minutes_remaining: 50
        label: "Lúpulo Amargor - 15g Magnum"
      - minutes_remaining: 1
        label: "Whirpool - 10min"
"""


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


# ── Parsing ───────────────────────────────────────────────────────────────

def test_parse_devices_yaml_le_os_7_devices():
    devices = svc.parse_devices_yaml(DEVICES_YAML)
    assert len(devices) == 7
    assert {d["id"] for d in devices} == {
        "mash_tun_temp", "boil_temp", "chiller_out_temp",
        "mash_heater", "boil_heater", "pump_b1", "pump_b2",
    }


def test_parse_devices_yaml_invalido_levanta_erro():
    with pytest.raises(svc.BridgeImportError):
        svc.parse_devices_yaml("mqtt:\n  enabled: true\n")  # sem chave 'devices'


def test_parse_recipe_yaml_le_vessels_e_steps():
    recipe = svc.parse_recipe_yaml(RECIPE_YAML)
    assert recipe["name"] == "Lagers da Casa"
    assert len(recipe["vessels"]) == 2
    assert len(recipe["steps"]) == 4


# ── Import completo (devices + recipe) ───────────────────────────────────────

def test_import_completo_cria_functions_e_actors(app):
    with app.app_context():
        result = svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)

        assert len(result["functions_created"]) == 7
        assert len(result["actors_created"]) == 7

        mash_temp = DeviceFunction.query.filter_by(name="mash_tun_temp").first()
        assert mash_temp.category == "sensor"
        assert mash_temp.data_type == "float"
        assert mash_temp.unit == "°C"
        assert mash_temp.min_value == 0
        assert mash_temp.max_value == 120

        mash_heater = DeviceFunction.query.filter_by(name="mash_heater").first()
        assert mash_heater.category == "actuator"
        assert mash_heater.data_type == "bool"

        actor = DeviceActor.query.filter_by(function_id=mash_heater.id).first()
        assert actor.is_risk is True
        assert actor.failsafe_value == "False"
        assert actor.port_name == "GPIO17"

        # sensores 1-Wire compartilhando pino - port_name usa o address, não o pin repetido
        actor_temp = DeviceActor.query.filter_by(function_id=mash_temp.id).first()
        assert actor_temp.port_name == "28-0000071234ab"


def test_import_completo_cria_um_unico_bridge_device(app):
    with app.app_context():
        svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)
        assert DeviceMetadata.query.filter_by(name="Bridge Principal").count() == 1
        assert DeviceActor.query.filter_by(device_id=DeviceMetadata.query.first().id).count() == 7


def test_import_completo_cria_planta_vasilhames_e_mapeamentos(app):
    with app.app_context():
        result = svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)

        plant = BrewPlant.query.get(result["plant_id"])
        assert plant.name == "Lagers da Casa"

        vessels = BrewPlantVessel.query.filter_by(plant_id=plant.id).order_by(BrewPlantVessel.position_order).all()
        assert [v.label_text for v in vessels] == ["Mash", "Boil"]
        assert vessels[0].vessel_type == "mash_tun"
        assert vessels[1].vessel_type == "boil_kettle"

        mash_mappings = {m.role_key: m.device_function_name for m in BrewPlantMapping.query.filter_by(vessel_id=vessels[0].id)}
        assert mash_mappings["sensor_temp"] == "mash_tun_temp"
        assert mash_mappings["actor_heat"] == "mash_heater"
        assert mash_mappings["actor_pump_1"] == "pump_b1"

        boil_mappings = {m.role_key: m.device_function_name for m in BrewPlantMapping.query.filter_by(vessel_id=vessels[1].id)}
        assert boil_mappings["sensor_temp"] == "boil_temp"
        assert boil_mappings["actor_heat"] == "boil_heater"
        assert boil_mappings["actor_pump_1"] == "pump_b2"


def test_import_completo_conecta_tubulacao_via_bomba_do_vasilhame_seguinte(app):
    with app.app_context():
        result = svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)
        plant = BrewPlant.query.get(result["plant_id"])
        connections = plant.plant_schema_json["connections"]
        assert len(connections) == 1
        assert connections[0]["flow_function_name"] == "pump_b2"


def test_import_completo_cria_dashboard_com_widget_por_vasilhame(app):
    with app.app_context():
        result = svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)

        layout = DashboardLayout.query.get(result["layout_id"])
        assert layout.name == "Painel de Mostura"
        assert layout.plant_id == result["plant_id"]
        assert layout.is_default is True

        widgets = DashboardWidget.query.filter_by(layout_id=layout.id).all()
        vessel_widgets = [w for w in widgets if w.widget_type == "vessel"]
        alarm_widgets = [w for w in widgets if w.widget_type == "alarm_list"]
        assert len(vessel_widgets) == 2
        assert len(alarm_widgets) == 1
        assert {w.label_text for w in vessel_widgets} == {"Mash", "Boil"}


def test_import_so_devices_sem_recipe_nao_cria_planta(app):
    with app.app_context():
        result = svc.import_bridge_config(DEVICES_YAML)
        assert result["plant_id"] is None
        assert result["layout_id"] is None
        assert len(result["functions_created"]) == 7


# ── Idempotência ──────────────────────────────────────────────────────────

def test_rodar_import_duas_vezes_nao_duplica(app):
    with app.app_context():
        svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)
        result2 = svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML)

        assert result2["functions_created"] == []
        assert len(result2["functions_reused"]) == 7
        assert result2["vessels_created"] == []
        assert len(result2["vessels_reused"]) == 2
        assert result2["widgets_created"] == []
        assert len(result2["widgets_reused"]) == 3  # 2 vasilhames + alarm_list

        assert DeviceFunction.query.count() == 7
        assert BrewPlant.query.count() == 1
        assert DashboardLayout.query.count() == 1


def test_segundo_layout_importado_nao_vira_default(app):
    with app.app_context():
        svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML, layout_name="Painel 1")
        svc.import_bridge_config(DEVICES_YAML, RECIPE_YAML, layout_name="Painel 2", plant_name="Lagers da Casa")

        painel1 = DashboardLayout.query.filter_by(name="Painel 1").first()
        painel2 = DashboardLayout.query.filter_by(name="Painel 2").first()
        assert painel1.is_default is True
        assert painel2.is_default is False


# ── Rotas web ────────────────────────────────────────────────────────────────

def test_form_get(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/bridge-import/")
    assert resp.status_code == 200
    assert b"Cadastro Prim" in resp.data


def test_post_sem_devices_yaml_falha_com_flash(app, client):
    _login_admin(app, client)
    resp = client.post("/brewstation/bridge-import/", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert "obrigat".encode("utf-8") in resp.data.lower() or b"obrigat" in resp.data


def test_post_com_devices_e_recipe_via_textarea(app, client):
    _login_admin(app, client)
    resp = client.post("/brewstation/bridge-import/", data={
        "devices_text": DEVICES_YAML, "recipe_text": RECIPE_YAML,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Ver Dashboard" in resp.data

    with app.app_context():
        assert DeviceFunction.query.count() == 7
        assert BrewPlant.query.filter_by(name="Lagers da Casa").first() is not None
