"""Duplicação de amostras e compatibilidade da antiga URL de starters."""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        user = User(username="admin", email="admin@test.local", nome="Admin",
                    nome_completo="Administrador", celular="11999999999",
                    is_admin=True, is_active=True)
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


def _sample(client):
    strain = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"}).get_json()["item"]
    device = client.post("/api/brewstation/yeast-storage-devices/", json={"name": "Freezer"}).get_json()["item"]
    container = client.post("/api/brewstation/yeast-containers/", json={"name": "Caixa A", "device_id": device["id"]}).get_json()["item"]
    item = client.post("/api/brewstation/yeast-bank-items/", json={
        "strain_id": strain["id"], "storage_type": "Agar Inclinado",
        "container_id": container["id"], "location": "Freezer", "storage_slot": "A1",
        "label_text": "Lote original", "prepared_date": "2026-10-01", "expiry_date": "2027-01-01",
    }).get_json()["item"]
    return item, container


def test_duplicate_preserva_origem_e_nao_copia_historico(app, client):
    _login_admin(app, client)
    item, container = _sample(client)
    event = client.post("/api/brewstation/yeast-bank-events/", json={
        "bank_item_id": item["id"], "event_type": "Starter", "event_date": "2026-10-02",
        "notes": "histórico original", "starter_status": "planned",
    })
    assert event.status_code in (200, 201)

    response = client.post(f"/brewstation/yeast-bank-items/{item['id']}/duplicate", data={
        "storage_type": "Agar Inclinado", "container_id": str(container["id"]),
        "location": "Freezer", "storage_slot": "A2", "label_text": "Lote duplicado",
        "prepared_date": "2026-10-01", "expiry_date": "2027-01-01",
        "return_to": "/brewstation/yeast-bank-items/?q=US-05&page=2",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("?q=US-05&page=2")

    with app.app_context():
        items = YeastBankItem.query.order_by(YeastBankItem.id).all()
        assert len(items) == 2
        original, duplicate = items
        assert original.storage_slot == "A1"
        assert duplicate.strain_id == original.strain_id
        assert duplicate.storage_slot == "A2"
        assert duplicate.label_text == "Lote duplicado"
        assert duplicate.status == "active"
        assert duplicate.identification != original.identification
        assert duplicate.estimated_viability_pct is None
        assert YeastBankEvent.query.filter_by(bank_item_id=duplicate.id).count() == 0


def test_duplicate_rejeita_referencia_invalida_sem_criar_registro(app, client):
    _login_admin(app, client)
    item, _ = _sample(client)
    with app.app_context():
        before = YeastBankItem.query.count()
    response = client.post(f"/brewstation/yeast-bank-items/{item['id']}/duplicate", data={
        "storage_type": "Agar Inclinado", "container_id": "999999", "storage_slot": "A2",
    })
    assert response.status_code == 302
    with app.app_context():
        assert YeastBankItem.query.count() == before


def test_url_legada_redireciona_para_eventos_filtrados(app, client):
    _login_admin(app, client)
    response = client.get("/brewstation/yeast-starter-logs")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/brewstation/yeast-bank-events/?filter_event_type=Starter")


def test_sync_desativa_transacao_legada_do_menu(app):
    from model.core.transaction import Transaction
    with app.app_context():
        legacy = Transaction(code="TX_YEAST_STARTER_LOGS", label="Starters",
                             route="/brewstation/yeast-starter-logs", source_module="brewstation",
                             is_standard=False, is_active=True)
        db.session.add(legacy)
        db.session.commit()
        app.module_manager._pending_transactions.append((
            {"code": "TX_YEAST_STARTER_LOGS", "label": "Starters",
             "route": "/brewstation/yeast-starter-logs"}, "brewstation",
        ))
        app.module_manager.sync_all_transactions()
        legacy = Transaction.query.filter_by(code="TX_YEAST_STARTER_LOGS").one()
        assert legacy.is_active is False
