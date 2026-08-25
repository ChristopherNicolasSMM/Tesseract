"""
tests/test_phase5b_yeast_bank_full.py

Cobre as 7 entidades restantes de yeast_bank (Fase 5b): tabelas com
prefixo correto, FK entre tabelas da mesma Feature resolvendo certo
(cadeia strain -> device -> bank_item -> starter_log), e permissões
sincronizadas para todas.
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


def test_todas_as_tabelas_de_yeast_bank_existem_com_prefixo_correto(app):
    esperado = {
        "tesseract_brewstation_yeastbank_strain",
        "tesseract_brewstation_yeastbank_storage_device",
        "tesseract_brewstation_yeastbank_bank_item",
        "tesseract_brewstation_yeastbank_cell_count_history",
        "tesseract_brewstation_yeastbank_bank_event",
        "tesseract_brewstation_yeastbank_bank_config",
        "tesseract_brewstation_yeastbank_container",
    }
    with app.app_context():
        existentes = set(db.metadata.tables.keys())
        assert esperado.issubset(existentes)


def test_permissoes_camada_1_existem_para_todas_as_6_entidades_novas(app):
    from model.core.permission import Permission

    with app.app_context():
        nomes = {p.name for p in Permission.query.all()}
        plurals = [
            "yeast_storage_devices", "yeast_bank_items",
            "yeast_cell_count_histories", "yeast_bank_events",
            "yeast_bank_configs", "yeast_containers",
        ]
        for plural in plurals:
            for action in ("list", "detail", "create", "update", "trash", "restore", "delete_permanent"):
                assert f"{plural}.{action}" in nomes


def test_cadeia_de_fk_strain_device_container_item_starter_via_http(app, client):
    # Cadeia pós skill 19: strain + device -> container -> item -> evento
    # (bank_item não referencia mais storage_device_id diretamente, ver
    # docs/skills/19-proposta-reestruturacao-yeast-bank-container.md).
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    assert r.status_code == 201
    strain_id = r.get_json()["item"]["id"]

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer 1"})
    assert r.status_code == 201
    device_id = r.get_json()["item"]["id"]

    r = client.post(
        "/api/brewstation/yeast-containers/",
        json={"name": "Caixa 1", "device_id": device_id},
    )
    assert r.status_code == 201
    container_data = r.get_json()["item"]
    container_id = container_data["id"]
    # FK resolvida E serializada — confirma relationship() funcionando, não só a coluna
    assert container_data["device"]["name"] == "Freezer 1"

    r = client.post(
        "/api/brewstation/yeast-bank-items/",
        json={"strain_id": strain_id, "storage_type": "slant", "container_id": container_id},
    )
    assert r.status_code == 201
    item_data = r.get_json()["item"]
    item_id = item_data["id"]
    # FK resolvida E serializada — confirma relationship() funcionando, não só a coluna
    assert item_data["strain"]["name"] == "US-05"

    # skill 22: Starter foi fundido em YeastBankEvent — não existe mais
    # tabela/tela separada, os campos (target_volume_l, objective etc.)
    # ficam direto no evento quando event_type="Starter".
    r = client.post(
        "/api/brewstation/yeast-bank-events/",
        json={"bank_item_id": item_id, "event_type": "Starter", "objective": "propagacao"},
    )
    assert r.status_code == 201
    event_data = r.get_json()["item"]
    assert event_data["bank_item_id"] == item_id
    assert event_data["objective"] == "propagacao"


def test_bank_config_eh_um_crud_normal_sem_fk(app, client):
    _login_admin(app, client)

    r = client.post(
        "/api/brewstation/yeast-bank-configs/",
        json={"storage_type": "Seca", "expiry_days": 365, "daily_viability_loss_pct": 0.2},
    )
    assert r.status_code == 201
    assert r.get_json()["item"]["expiry_days"] == 365


def test_soft_delete_funciona_em_entidade_nova(app, client):
    _login_admin(app, client)

    r = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer 3"})
    device_id = r.get_json()["item"]["id"]

    r = client.post(f"/api/brewstation/yeast-storage-devices/{device_id}/trash")
    assert r.status_code == 200

    r = client.get("/api/brewstation/yeast-storage-devices/")
    assert all(i["id"] != device_id for i in r.get_json()["items"])

    r = client.post(f"/api/brewstation/yeast-storage-devices/{device_id}/restore")
    assert r.status_code == 200

    r = client.get("/api/brewstation/yeast-storage-devices/")
    assert any(i["id"] == device_id for i in r.get_json()["items"])
