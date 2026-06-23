"""
tests/test_phase2_rbac.py

Cobre: criação de usuário admin, has_permission, login/logout,
permission_required (401 sem login, 403 sem permissão, 200 com
permissão), soft-delete (deactivate/activate), validação de CPF.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.role import Role
from model.core.permission import Permission


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_admin(app, username="admin"):
    with app.app_context():
        user = User(
            username=username, email=f"{username}@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username="admin", password="senha123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_com_credenciais_validas(app, client):
    _create_admin(app)
    resp = _login(client)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_login_com_senha_errada(app, client):
    _create_admin(app)
    resp = _login(client, password="errada")
    assert resp.status_code == 401


def test_acesso_sem_login_retorna_401(client):
    resp = client.get("/api/admin/users/")
    assert resp.status_code == 401


def test_admin_tem_acesso_a_rota_protegida(app, client):
    _create_admin(app)
    _login(client)
    resp = client.get("/api/admin/users/")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_usuario_sem_permissao_recebe_403(app, client):
    with app.app_context():
        user = User(
            username="comum", email="comum@test.local",
            nome="Comum", nome_completo="Usuário Comum", celular="11988888888",
            is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()

    _login(client, username="comum")
    resp = client.get("/api/admin/users/")
    assert resp.status_code == 403


def test_has_permission_via_role(app):
    with app.app_context():
        perm = Permission(name="recipes.trash")
        role = Role(name="brewmaster")
        role.permissions.append(perm)

        user = User(
            username="brewer", email="brewer@test.local",
            nome="Brewer", nome_completo="Cervejeiro", celular="11977777777",
            is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        user.roles.append(role)

        db.session.add_all([perm, role, user])
        db.session.commit()

        assert user.has_permission("recipes.trash") is True
        assert user.has_permission("recipes.delete_permanent") is False


def test_soft_delete_deactivate_activate(app, client):
    """
    Admin desativa/reativa OUTRO usuário — não a si mesmo.

    Nota de comportamento (não é bug): UserMixin.is_authenticated do
    Flask-Login é definido como `return self.is_active`. Se o admin se
    autodesativasse, a própria sessão dele perderia autenticação na
    requisição seguinte. É o comportamento de segurança correto —
    só não é o cenário que este teste cobre.
    """
    _create_admin(app, username="admin")
    with app.app_context():
        target = User(
            username="alvo", email="alvo@test.local",
            nome="Alvo", nome_completo="Usuário Alvo", celular="11966666666",
            is_admin=False, is_active=True,
        )
        target.set_password("senha123")
        db.session.add(target)
        db.session.commit()
        target_id = target.id

    _login(client, username="admin")

    resp = client.post(f"/api/admin/users/{target_id}/deactivate")
    assert resp.status_code == 200

    with app.app_context():
        assert User.query.get(target_id).is_active is False

    resp = client.post(f"/api/admin/users/{target_id}/activate")
    assert resp.status_code == 200

    with app.app_context():
        assert User.query.get(target_id).is_active is True


def test_autodesativacao_invalida_a_propria_sessao(app, client):
    """
    Documenta o comportamento real do Flask-Login (ver nota acima):
    se um usuário desativa a própria conta, a sessão dele desautentica
    na requisição seguinte — sem precisar de logout explícito.
    """
    user_id = _create_admin(app)
    _login(client)

    resp = client.post(f"/api/admin/users/{user_id}/deactivate")
    assert resp.status_code == 200

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_cpf_invalido_eh_rejeitado(app):
    with app.app_context():
        user = User(
            username="cpf_test", email="cpf@test.local",
            nome="X", nome_completo="X X", celular="11900000000",
        )
        with pytest.raises(ValueError):
            user.set_cpf("111.111.111-11")  # sequência repetida, sempre inválida


def test_cpf_valido_eh_formatado(app):
    with app.app_context():
        user = User(
            username="cpf_test2", email="cpf2@test.local",
            nome="X", nome_completo="X X", celular="11900000000",
        )
        # CPF válido conhecido (gerado para teste, dígitos verificadores corretos)
        user.set_cpf("11144477735")
        assert user.cpf == "111.444.777-35"
