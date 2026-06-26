"""
tests/test_phase6a_device_manager.py

Cobre feature_device_manager: tabelas com prefixo correto, PK Integer
+ external_id UUID (skill 02), relationship() funcionando (melhoria
sobre o BrewStation original, que desabilitava de propósito), e o
bug do `default={}` mutável corrigido em EmulatedDevice.
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


def test_4_tabelas_de_device_manager_existem_com_prefixo_correto(app):
    esperado = {
        "tesseract_dvm_function",
        "tesseract_dvm_device",
        "tesseract_dvm_actor",
        "tesseract_dvm_emulated_device",
    }
    with app.app_context():
        assert esperado.issubset(set(db.metadata.tables.keys()))


def test_device_metadata_tem_id_integer_e_external_id_uuid(app, client):
    _login_admin(app, client)

    r = client.post("/api/device-manager/device-metadatas/", json={"name": "Freezer Teste"})
    assert r.status_code == 201
    item = r.get_json()["item"]

    assert isinstance(item["id"], int)
    assert len(item["external_id"]) == 36  # formato UUID (com hífens)
    assert item["external_id"].count("-") == 4


def test_dois_devices_tem_external_ids_diferentes(app, client):
    _login_admin(app, client)

    r1 = client.post("/api/device-manager/device-metadatas/", json={"name": "Device 1"})
    r2 = client.post("/api/device-manager/device-metadatas/", json={"name": "Device 2"})

    assert r1.get_json()["item"]["external_id"] != r2.get_json()["item"]["external_id"]


def test_relationship_funciona_entre_actor_device_e_function(app, client):
    """
    No BrewStation original, relationship() era desabilitado de
    propósito porque o mecanismo de prefixo dele quebrava a
    configuração do mapper. Aqui isso foi corrigido — este teste
    confirma o relationship() funcionando de fato via ORM.
    """
    _login_admin(app, client)

    with app.app_context():
        from addons.addon_device_manager.root.model.device_function import DeviceFunction
        from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
        from addons.addon_device_manager.root.model.device_actor import DeviceActor

        function = DeviceFunction(name="temp", display_name="Temperatura", category="sensor")
        device = DeviceMetadata(name="Freezer X")
        db.session.add_all([function, device])
        db.session.commit()

        actor = DeviceActor(
            device_id=device.id, function_id=function.id,
            port_name="GPIO1", actor_type="sensor", name="Sensor X",
        )
        db.session.add(actor)
        db.session.commit()

        # Acesso via ORM relationship(), não via query manual
        assert actor.device.name == "Freezer X"
        assert actor.function.display_name == "Temperatura"
        # backref também funciona nos dois sentidos
        assert actor in device.actors
        assert actor in function.actors


def test_emulated_device_functions_config_nao_compartilha_dict_mutavel(app):
    """
    Bug original: default={} no Column compartilhava o MESMO dict
    entre todas as instâncias sem valor explícito. Corrigido com
    default=lambda: {}.
    """
    with app.app_context():
        from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
        from addons.addon_device_manager.root.model.emulated_device import EmulatedDevice

        device = DeviceMetadata(name="Device Y")
        db.session.add(device)
        db.session.commit()

        em1 = EmulatedDevice(device_id=device.id, emulation_mode="sine_wave")
        em2 = EmulatedDevice(device_id=device.id, emulation_mode="random_walk")
        db.session.add_all([em1, em2])
        db.session.commit()

        em1.functions_config["temp"] = 25.0
        db.session.commit()

        db.session.refresh(em2)
        assert em2.functions_config == {} or em2.functions_config is None


def test_soft_delete_em_device_metadata(app, client):
    _login_admin(app, client)

    r = client.post("/api/device-manager/device-metadatas/", json={"name": "Device Trash"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(f"/api/device-manager/device-metadatas/{device_id}/trash")
    assert r.status_code == 200

    r = client.get("/api/device-manager/device-metadatas/")
    assert all(i["id"] != device_id for i in r.get_json()["items"])
