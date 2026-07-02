"""
tests/test_menu_hierarquico.py

Cobre a skill 10 (menu hierárquico): Transaction.is_folder,
parent_id/order_index, e a tela admin_transactions.py com seletor de
pai em vez de texto livre de grupo.
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


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Model ────────────────────────────────────────────────────────────────

def test_is_folder_true_quando_route_none(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        assert tx.is_folder is True


def test_is_folder_false_quando_tem_rota(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_HOME").first()
        assert tx.is_folder is False


def test_parent_relationship_funciona(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_ROLES").first()
        assert tx.parent is not None
        assert tx.parent.code == "TX_GROUP_ADMIN"
        assert tx in tx.parent.children


def test_catalogo_core_nao_tem_mais_coluna_group():
    """Não-regressão: garante que ninguém reintroduziu `group` no model."""
    assert not hasattr(Transaction, "group")


# ── admin_transactions.py: seletor de pai ───────────────────────────────

def test_criar_transacao_manual_com_pai(app, client):
    _login_admin(app, client)
    with app.app_context():
        admin_folder = Transaction.query.filter_by(code="TX_GROUP_ADMIN").first()
        parent_id = admin_folder.id

    resp = client.post(
        "/admin/transactions/",
        data={
            "code": "TX_MEU_LINK", "label": "Meu Link",
            "parent_id": str(parent_id), "route": "/meu-link",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_MEU_LINK").first()
        assert tx is not None
        assert tx.parent.code == "TX_GROUP_ADMIN"


def test_criar_transacao_manual_sem_rota_vira_pasta(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/transactions/",
        data={"code": "TX_MINHA_PASTA", "label": "Minha Pasta"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_MINHA_PASTA").first()
        assert tx is not None
        assert tx.is_folder is True


def test_nova_pasta_manual_fica_disponivel_como_pai(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/transactions/",
        data={"code": "TX_PASTA_NOVA", "label": "Pasta Nova"},
        follow_redirects=True,
    )
    with app.app_context():
        pasta = Transaction.query.filter_by(code="TX_PASTA_NOVA").first()
        pasta_id = pasta.id

    resp = client.post(
        "/admin/transactions/",
        data={
            "code": "TX_FILHO_DA_PASTA_NOVA", "label": "Filho",
            "parent_id": str(pasta_id), "route": "/filho",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        filho = Transaction.query.filter_by(code="TX_FILHO_DA_PASTA_NOVA").first()
        assert filho.parent_id == pasta_id


def test_excluir_pasta_com_filhos_falha(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/transactions/",
        data={"code": "TX_PASTA_COM_FILHO", "label": "Pasta Com Filho"},
        follow_redirects=True,
    )
    with app.app_context():
        pasta = Transaction.query.filter_by(code="TX_PASTA_COM_FILHO").first()
        pasta_id = pasta.id

    client.post(
        "/admin/transactions/",
        data={
            "code": "TX_FILHO_X", "label": "Filho X",
            "parent_id": str(pasta_id), "route": "/filho-x",
        },
        follow_redirects=True,
    )

    resp = client.post(f"/admin/transactions/{pasta_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Transaction.query.get(pasta_id) is not None  # não foi excluída


def test_transacao_de_codigo_nao_permite_editar_pai(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_HOME").first()
        tx_id = tx.id
        original_parent_id = tx.parent_id

    resp = client.post(
        f"/admin/transactions/{tx_id}",
        data={"label": "Início Hackeado", "route": "/", "parent_id": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        tx = Transaction.query.get(tx_id)
        assert tx.label == "Início"  # não mudou — é code-sourced
        assert tx.parent_id == original_parent_id


def test_tela_manage_carrega_com_breadcrumb(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/transactions/?q=TX_ADMIN_ROLES")
    assert resp.status_code == 200
    assert "Admin &gt; Papéis e Permissões".encode() in resp.data
