"""
tests/test_phase14_yeast_container.py

Cobre a entidade YeastContainer (skill 19 —
docs/skills/19-proposta-reestruturacao-yeast-bank-container.md): tabela
criada com o prefixo correto, Container sempre físico (device_id
obrigatório), YeastBankItem.container_id obrigatório (sem
storage_device_id direto) e listagem de itens filtrada por container.
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


def test_tabela_container_existe_com_prefixo_correto(app):
    with app.app_context():
        assert "tesseract_brewstation_yeastbank_container" in db.metadata.tables.keys()


def test_container_exige_device_id_sempre_fisico(app, client):
    _login_admin(app, client)

    # Sem device_id — Container é sempre físico (skill 19, decisão descartada:
    # container virtual). Deve falhar.
    r = client.post("/api/brewstation/yeast-containers/", json={"name": "Caixa órfã"})
    assert r.status_code != 201


def test_container_criado_e_vinculado_ao_device(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer A"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "container_type": "Caixa", "device_id": device_id},
    )
    assert r.status_code == 201
    data = r.get_json()["item"]
    assert data["device_id"] == device_id
    assert data["device"]["name"] == "Freezer A"


def test_bank_item_exige_container_id_nao_aceita_storage_device_id_direto(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    strain_id = r.get_json()["item"]["id"]

    # Sem container_id — deve falhar (container_id é NOT NULL desde a
    # reestruturação da skill 19).
    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant"},
    )
    assert r.status_code != 201


def test_listagem_de_itens_permite_filtrar_por_container(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "WLP001"})
    strain_id = r.get_json()["item"]["id"]

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Geladeira 1"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Estante A", "container_type": "Estante", "device_id": device_id},
    )
    container_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    assert r.status_code == 201
    item_id = r.get_json()["item"]["id"]

    r = client.get(f"/api/brewstation/yeast-bank-items/?container_id={container_id}")
    assert r.status_code == 200
    ids = [i["id"] for i in r.get_json()["items"]]
    assert item_id in ids
