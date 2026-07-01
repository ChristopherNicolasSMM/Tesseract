"""
tests/test_menu_preferences.py

Cobre a skill 07: resolução de ordem/colapso (usuário > global >
ordem original), persistência via API, e a tela admin de padrão
global.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.role import Role
from model.core.permission import Permission
from services.core import menu_preference_service as svc


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
        user_id = User.query.filter_by(username="admin").first().id
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return user_id


# ── Resolução de estado ──────────────────────────────────────────────────

def test_sem_nenhuma_preferencia_usa_ordem_original(app):
    with app.app_context():
        state = svc.resolve_menu_state(None, ["Ferramentas de Desenvolvimento", "Admin"])
        assert state["ordered_groups"] == ["Ferramentas de Desenvolvimento", "Admin"]
        assert state["collapsed_groups"] == set()
        assert state["sidebar_collapsed"] is False


def test_padrao_global_sobrepoe_ordem_original(app):
    with app.app_context():
        svc.set_global_defaults(
            group_order=["Admin", "Ferramentas de Desenvolvimento"],
            default_collapsed_groups=["Admin"],
            default_sidebar_collapsed=True,
        )
        state = svc.resolve_menu_state(None, ["Ferramentas de Desenvolvimento", "Admin"])
        assert state["ordered_groups"] == ["Admin", "Ferramentas de Desenvolvimento"]
        assert state["collapsed_groups"] == {"Admin"}
        assert state["sidebar_collapsed"] is True


def test_override_do_usuario_sobrepoe_padrao_global(app):
    with app.app_context():
        admin = User(username="menu_user", email="menu_user@test.local", nome="Menu",
                     nome_completo="Menu User", celular="0", is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()
        user_id = admin.id

        svc.set_global_defaults(
            group_order=["Admin", "Ferramentas de Desenvolvimento"],
            default_sidebar_collapsed=True,
        )
        svc.save_user_preference(
            user_id,
            group_order=["Ferramentas de Desenvolvimento", "Admin"],
            sidebar_collapsed=False,
        )

        state = svc.resolve_menu_state(user_id, ["Ferramentas de Desenvolvimento", "Admin"])
        assert state["ordered_groups"] == ["Ferramentas de Desenvolvimento", "Admin"]
        assert state["sidebar_collapsed"] is False  # override do usuário venceu


def test_grupo_novo_sem_posicao_salva_vai_pro_fim(app):
    with app.app_context():
        svc.set_global_defaults(group_order=["Admin"])
        state = svc.resolve_menu_state(None, ["Admin", "Ferramentas de Desenvolvimento", "Grupo Novo"])
        assert state["ordered_groups"][0] == "Admin"
        assert set(state["ordered_groups"][1:]) == {"Ferramentas de Desenvolvimento", "Grupo Novo"}


# ── API de preferência do usuário ───────────────────────────────────────

def test_salvar_preferencia_via_api(app, client):
    user_id = _login_admin(app, client)

    resp = client.post(
        "/api/menu-preference",
        json={"sidebar_collapsed": True, "collapsed_groups": ["Admin"]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        from model.core.user_menu_preference import UserMenuPreference
        pref = UserMenuPreference.query.filter_by(user_id=user_id).first()
        assert pref.sidebar_collapsed is True
        assert pref.collapsed_groups_json == ["Admin"]


def test_api_de_preferencia_exige_login(client):
    resp = client.post("/api/menu-preference", json={"sidebar_collapsed": True})
    assert resp.status_code in (302, 401)


# ── Tela admin de padrão global ─────────────────────────────────────────

def test_tela_menu_settings_carrega_para_admin(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/menu-settings/")
    assert resp.status_code == 200
    assert b"Configura\xc3\xa7\xc3\xb5es de Menu" in resp.data


def test_tela_menu_settings_bloqueada_sem_permissao(app, client):
    with app.app_context():
        user = User(username="sem_permissao", email="sp@test.local", nome="Sem Permissao",
                     nome_completo="Sem Permissao", celular="0", is_active=True, is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "sem_permissao", "password": "x"})
    resp = client.get("/admin/menu-settings/")
    assert resp.status_code == 403


def test_salvar_padrao_global_via_form(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/menu-settings/",
        data={
            "group_order": ["Admin", "Ferramentas de Desenvolvimento"],
            "default_collapsed_groups": ["Ferramentas de Desenvolvimento"],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert svc.get_global_group_order() == ["Admin", "Ferramentas de Desenvolvimento"]
        assert svc.get_global_default_collapsed_groups() == ["Ferramentas de Desenvolvimento"]
        assert svc.get_global_default_sidebar_collapsed() is False


# ── Permissão fixa seedada no boot ──────────────────────────────────────

def test_permissao_menu_settings_seedada_no_boot(app):
    with app.app_context():
        assert Permission.query.filter_by(name="system_config.menu_settings").first() is not None
