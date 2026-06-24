"""
tests/test_phase7a_transactions.py

Cobre o catálogo de transações: seed de Core, sincronização de
transações contribuídas por Addon/Feature (idempotente), filtro real
por has_permission() (não um tier separado), e a regra de que
is_active nunca é sobrescrita pelo sync.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_catalogo_core_eh_seedado(app):
    with app.app_context():
        codes = {t.code for t in Transaction.query.filter_by(is_standard=True).all()}
        assert "TX_HOME" in codes
        assert "TX_ADMIN_USERS" in codes


def test_transacoes_de_addon_sao_sincronizadas(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_YEAST_BANK").first()
        assert tx is not None
        assert tx.is_standard is False
        assert tx.source_module == "brewstation"
        assert tx.permission_required == "yeast_strains.list"


def test_sync_eh_idempotente_nao_duplica(app):
    with app.app_context():
        count_antes = Transaction.query.filter_by(code="TX_YEAST_BANK").count()
        app.module_manager.sync_all_transactions()
        db.session.commit()
        count_depois = Transaction.query.filter_by(code="TX_YEAST_BANK").count()
        assert count_antes == count_depois == 1


def test_desativar_manualmente_sobrevive_ao_sync(app):
    """
    is_active é controlada pela UI/admin, não pelo sync de código —
    sync nunca deve reativar uma transação desativada manualmente.
    """
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_YEAST_BANK").first()
        tx.is_active = False
        db.session.commit()

        app.module_manager.sync_all_transactions()
        db.session.commit()

        tx_depois = Transaction.query.filter_by(code="TX_YEAST_BANK").first()
        assert tx_depois.is_active is False


def _create_user(app, *, is_admin: bool, username: str):
    with app.app_context():
        user = User(
            username=username, email=f"{username}@test.local",
            nome=username, nome_completo=username, celular="11999999999",
            is_admin=is_admin, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()


def test_admin_ve_todas_transacoes_ativas_via_api(app, client):
    _create_user(app, is_admin=True, username="admin")
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})

    resp = client.get("/api/core/transactions/")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.get_json()["transactions"]}
    assert "TX_YEAST_BANK" in codes
    assert "TX_ADMIN_USERS" in codes


def test_usuario_comum_so_ve_transacoes_sem_permissao_exigida(app, client):
    _create_user(app, is_admin=False, username="comum")
    client.post("/api/auth/login", json={"username": "comum", "password": "senha123"})

    resp = client.get("/api/core/transactions/")
    assert resp.status_code == 200
    codes = {t["code"] for t in resp.get_json()["transactions"]}
    assert codes == {"TX_HOME"}  # só a transação sem permission_required


def test_usuario_com_permissao_especifica_ve_a_transacao_correspondente(app, client):
    from model.core.role import Role
    from model.core.permission import Permission

    with app.app_context():
        perm = Permission.query.filter_by(name="yeast_strains.list").first()
        role = Role(name="yeast_viewer")
        role.permissions.append(perm)

        user = User(
            username="cervejeiro", email="cervejeiro@test.local",
            nome="Cervejeiro", nome_completo="Cervejeiro", celular="11999999999",
            is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        user.roles.append(role)
        db.session.add_all([role, user])
        db.session.commit()

    client.post("/api/auth/login", json={"username": "cervejeiro", "password": "senha123"})

    resp = client.get("/api/core/transactions/")
    codes = {t["code"] for t in resp.get_json()["transactions"]}
    assert "TX_YEAST_BANK" in codes
    assert "TX_DEVICE_MANAGER" not in codes  # não tem device_metadatas.list


def test_transacao_inativa_nao_aparece_nem_para_admin(app, client):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_YEAST_BANK").first()
        tx.is_active = False
        db.session.commit()

    _create_user(app, is_admin=True, username="admin2")
    client.post("/api/auth/login", json={"username": "admin2", "password": "senha123"})

    resp = client.get("/api/core/transactions/")
    codes = {t["code"] for t in resp.get_json()["transactions"]}
    assert "TX_YEAST_BANK" not in codes
