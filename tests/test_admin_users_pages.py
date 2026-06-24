"""
tests/test_admin_users_pages.py

Cobre as telas HTML de administração de usuários: criação, edição,
atribuição de Role, reset de senha, ativar/desativar (incluindo o
bloqueio de autodesativação), e a correção da rota de TX_ADMIN_USERS.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.role import Role


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client, username="admin"):
    with app.app_context():
        admin = User(
            username=username, email=f"{username}@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    client.post("/api/auth/login", json={"username": username, "password": "senha123"})
    return admin_id


def test_tx_admin_users_aponta_para_tela_html_nao_api(app):
    from model.core.transaction import Transaction

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_USERS").first()
        assert tx.route == "/admin/users"


def test_criar_usuario_pelo_formulario(app, client):
    _login_admin(app, client)

    resp = client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senha123",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"joao" in resp.data

    with app.app_context():
        assert User.query.filter_by(username="joao").first() is not None


def test_editar_usuario_pelo_formulario(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senha123",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    resp = client.post(
        f"/admin/users/{joao_id}",
        data={
            "username": "joao", "email": "joao@x.com",
            "nome": "Joao", "nome_completo": "Nome Editado", "celular": "11988888888",
        },
        follow_redirects=True,
    )
    assert b"Nome Editado" in resp.data


def test_editar_sem_senha_nao_apaga_senha_existente(app, client):
    """
    No formulário de edição, campo de senha em branco != trocar a
    senha por vazio — diferente da API JSON, que já tem esse cuidado
    só porque "password" nem é enviado.
    """
    _login_admin(app, client)
    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senhaoriginal",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    client.post(
        f"/admin/users/{joao_id}",
        data={
            "username": "joao", "email": "joao@x.com", "password": "",
            "nome": "Joao", "nome_completo": "Joao Editado", "celular": "11988888888",
        },
    )

    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "joao", "password": "senhaoriginal"})
    assert resp.get_json()["success"] is True


def test_atribuir_role_pelo_formulario(app, client):
    _login_admin(app, client)
    with app.app_context():
        role = Role(name="operador")
        db.session.add(role)
        db.session.commit()
        role_id = role.id

    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senha123",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    client.post(f"/admin/users/{joao_id}/roles", data={"role_ids": [str(role_id)]})

    with app.app_context():
        joao = User.query.get(joao_id)
        assert "operador" in [r.name for r in joao.roles]


def test_reset_de_senha_pela_tela(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senhaantiga",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    resp = client.post(
        f"/admin/users/{joao_id}/reset-password",
        data={"new_password": "senhanova123"},
        follow_redirects=True,
    )
    assert b"redefinida" in resp.data

    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "joao", "password": "senhanova123"})
    assert resp.get_json()["success"] is True


def test_reset_de_senha_exige_minimo_6_caracteres(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senha123",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    resp = client.post(
        f"/admin/users/{joao_id}/reset-password",
        data={"new_password": "123"},
        follow_redirects=True,
    )
    assert b"pelo menos 6 caracteres" in resp.data


def test_desativar_outro_usuario(app, client):
    _login_admin(app, client)
    client.post(
        "/admin/users/",
        data={
            "username": "joao", "email": "joao@x.com", "password": "senha123",
            "nome": "Joao", "nome_completo": "Joao Silva", "celular": "11988888888",
        },
    )
    with app.app_context():
        joao_id = User.query.filter_by(username="joao").first().id

    resp = client.post(f"/admin/users/{joao_id}/deactivate", follow_redirects=True)
    assert b"desativado" in resp.data

    with app.app_context():
        assert User.query.get(joao_id).is_active is False


def test_autodesativacao_eh_bloqueada_na_tela(app, client):
    """
    Diferente da API (Fase 2), a TELA bloqueia explicitamente a
    autodesativação — evita o usuário se trancar fora sem entender
    por quê (UserMixin.is_authenticated == self.is_active).
    """
    admin_id = _login_admin(app, client)

    resp = client.post(f"/admin/users/{admin_id}/deactivate", follow_redirects=True)
    assert "não pode desativar sua própria conta".encode("utf-8") in resp.data

    with app.app_context():
        assert User.query.get(admin_id).is_active is True
