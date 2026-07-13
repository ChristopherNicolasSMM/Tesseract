"""
tests/test_weak_ref_value_field.py

Cobre a extensão da skill 11 (value_field) — achado real na conversa
do Dashboard de Brassagem: por padrão o combo de referência fraca
guarda o `id` (PK) do alvo, mas alguns campos guardam outra coluna
(ex.: DashboardWidget.device_function_name guarda DeviceFunction.name,
não .id — skill 02, referência fraca cross-Addon sempre por nome).

- /api/options/<plural>?value_field=... aceita e valida contra
  colunas reais do model alvo.
- Resolvers novos (get_function_by_id, get_device_metadata,
  mash_control_lookups.*) devolvem a chave "display" obrigatória.
- @weak_ref aplicado a FK real DENTRO da mesma Feature/Addon
  (DashboardLayout.plant_id, DashboardWidget.vessel_id/layout_id,
  DeviceActor.device_id/function_id) e a referência fraca cross-Addon
  de sempre (DashboardWidget/BrewPlantMapping.device_function_name).
- Formulário de CRIAÇÃO inline (manage.html) também ganha o combo —
  antes só a tela de edição (detail.html) tinha.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from annotations import get_weak_refs
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.services import mash_control_lookups
from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
from addons.addon_device_manager.root.model.device_function import DeviceFunction
from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_function_lookup, device_metadata_lookup


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


def _criar_device_function(name="mash_temp", display_name="Temp. Mostura"):
    fn = DeviceFunction(name=name, display_name=display_name, category="sensor", data_type="float")
    db.session.add(fn)
    db.session.commit()
    return fn


def _criar_plant_vessel():
    plant = BrewPlant(name="Planta Teste")
    db.session.add(plant)
    db.session.commit()
    vessel = BrewPlantVessel(plant_id=plant.id, vessel_type="mash_tun", label_text="Mash Tun Teste")
    db.session.add(vessel)
    db.session.commit()
    return plant, vessel


# ── Resolvers novos devolvem "display" (contrato skill 11 §4) ───────────────

def test_get_function_by_id_devolve_display(app):
    with app.app_context():
        fn = _criar_device_function()
        resolved = device_function_lookup.get_function_by_id(fn.id)
        assert resolved["display"] == "Temp. Mostura"


def test_get_function_by_name_devolve_display(app):
    with app.app_context():
        _criar_device_function(name="mash_temp2", display_name="Temp. 2")
        resolved = device_function_lookup.get_function_by_name("mash_temp2")
        assert resolved["display"] == "Temp. 2"


def test_get_function_by_id_inexistente_devolve_none(app):
    with app.app_context():
        assert device_function_lookup.get_function_by_id(999999) is None


def test_get_device_metadata_devolve_display(app):
    with app.app_context():
        device = DeviceMetadata(name="Sensor HLT")
        db.session.add(device)
        db.session.commit()
        resolved = device_metadata_lookup.get_device_metadata(device.id)
        assert resolved["display"] == "Sensor HLT"


def test_mash_control_lookups_devolvem_display(app):
    with app.app_context():
        plant, vessel = _criar_plant_vessel()
        layout = DashboardLayout(name="Layout Teste")
        db.session.add(layout)
        db.session.commit()

        assert mash_control_lookups.get_plant(plant.id)["display"] == "Planta Teste"
        assert mash_control_lookups.get_vessel(vessel.id)["display"] == "Mash Tun Teste"
        assert mash_control_lookups.get_layout(layout.id)["display"] == "Layout Teste"


# ── @weak_ref declarado corretamente em cada model ───────────────────────────

def test_dashboard_widget_declara_3_weak_refs(app):
    with app.app_context():
        weak_refs = {wr["field"]: wr for wr in get_weak_refs(DashboardWidget)}
        assert set(weak_refs.keys()) == {"layout_id", "vessel_id", "device_function_name"}
        assert weak_refs["device_function_name"]["value_field"] == "name"
        assert weak_refs["device_function_name"]["options"] == "device_functions"
        assert weak_refs["vessel_id"]["value_field"] is None  # padrão "id", sem override
        assert weak_refs["vessel_id"]["options"] == "brew_plant_vessels"


def test_dashboard_layout_declara_weak_ref_plant_id(app):
    with app.app_context():
        weak_refs = get_weak_refs(DashboardLayout)
        assert len(weak_refs) == 1
        assert weak_refs[0]["field"] == "plant_id"
        assert weak_refs[0]["options"] == "brew_plants"


def test_brew_plant_mapping_declara_weak_ref_device_function_name_com_value_field(app):
    with app.app_context():
        weak_refs = {wr["field"]: wr for wr in get_weak_refs(BrewPlantMapping)}
        assert weak_refs["device_function_name"]["value_field"] == "name"


def test_device_actor_declara_2_weak_refs_padrao_id(app):
    with app.app_context():
        weak_refs = {wr["field"]: wr for wr in get_weak_refs(DeviceActor)}
        assert set(weak_refs.keys()) == {"device_id", "function_id"}
        assert weak_refs["device_id"]["value_field"] is None
        assert weak_refs["function_id"]["value_field"] is None


# ── /api/options com value_field ─────────────────────────────────────────────

def test_api_options_device_functions_com_value_field_name(app, client):
    _login_admin(app, client)
    with app.app_context():
        _criar_device_function(name="mash_temp3", display_name="Temperatura Mostura 3")

    resp = client.get("/api/options/device_functions?search=Mostura&value_field=name")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["results"]) == 1
    assert data["results"][0]["id"] == "mash_temp3"  # NAME, não o id inteiro
    assert data["results"][0]["text"] == "Temperatura Mostura 3"


def test_api_options_device_functions_sem_value_field_usa_id(app, client):
    _login_admin(app, client)
    with app.app_context():
        fn = _criar_device_function(name="mash_temp4", display_name="Temp 4")
        function_id = fn.id

    resp = client.get("/api/options/device_functions?search=Temp 4")
    data = resp.get_json()
    assert data["results"][0]["id"] == function_id  # padrão: id inteiro


def test_api_options_value_field_invalido_cai_pro_id(app, client):
    """value_field que não é coluna real do alvo é ignorado — nunca
    expõe atributo arbitrário (skill 11 §6, validação de segurança)."""
    _login_admin(app, client)
    with app.app_context():
        fn = _criar_device_function(name="mash_temp5", display_name="Temp 5")
        function_id = fn.id

    resp = client.get("/api/options/device_functions?search=Temp 5&value_field=coisa_que_nao_existe")
    data = resp.get_json()
    assert data["results"][0]["id"] == function_id


def test_api_options_brew_plants_combo_para_fk_real(app, client):
    """FK real dentro da mesma Feature também ganha o combo — não é
    exclusivo de referência fraca cross-Addon (achado desta rodada)."""
    _login_admin(app, client)
    with app.app_context():
        BrewPlant(name="Planta Combo Teste")
        db.session.add(BrewPlant(name="Planta Combo Teste"))
        db.session.commit()

    resp = client.get("/api/options/brew_plants?search=Combo")
    assert resp.status_code == 200
    assert len(resp.get_json()["results"]) == 1


# ── Telas reais (manage.html — criação inline — e detail.html) ──────────────

def test_form_de_criacao_de_dashboard_widget_tem_combo_para_os_3_campos(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/dashboard-widgets/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'data-weakref-source="dashboard_layouts"' in html
    assert 'data-weakref-source="brew_plant_vessels"' in html
    assert 'data-weakref-source="device_functions"' in html
    assert 'data-weakref-value-field="name"' in html  # só device_function_name


def test_form_de_criacao_de_dashboard_layout_tem_combo_de_planta(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/dashboard-layouts/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'data-weakref-source="brew_plants"' in html


def test_form_de_criacao_de_device_actor_tem_combo_device_e_function(app, client):
    _login_admin(app, client)
    resp = client.get("/device-manager/device-actors/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'data-weakref-source="device_metadatas"' in html
    assert 'data-weakref-source="device_functions"' in html


def test_criar_dashboard_widget_via_form_salva_device_function_name_correto(app, client):
    """Ponta a ponta: o valor que o combo guardaria (name, não id) é
    exatamente o que o create() espera receber no POST."""
    _login_admin(app, client)
    with app.app_context():
        _criar_device_function(name="mash_temp6", display_name="Temp 6")
        layout = DashboardLayout(name="Layout Form")
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.post("/brewstation/dashboard-widgets/", data={
        "layout_id": str(layout_id),
        "widget_type": "digital",
        "label_text": "Teste",
        "device_function_name": "mash_temp6",
        "x": "0", "y": "0", "width": "100", "height": "100",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        widget = DashboardWidget.query.filter_by(label_text="Teste").first()
        assert widget is not None
        assert widget.device_function_name == "mash_temp6"


def test_tela_de_detalhe_de_dashboard_layout_resolve_nome_da_planta(app, client):
    _login_admin(app, client)
    with app.app_context():
        plant, _ = _criar_plant_vessel()
        layout = DashboardLayout(name="Layout Detalhe", plant_id=plant.id)
        db.session.add(layout)
        db.session.commit()
        layout_id = layout.id

    resp = client.get(f"/brewstation/dashboard-layouts/{layout_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Planta Teste" in html
    assert 'data-weakref-source="brew_plants"' in html
