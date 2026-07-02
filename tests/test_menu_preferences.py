"""
tests/test_menu_preferences.py

Cobre a skill 07 + árvore (skill 10): resolução de ordem/colapso
(usuário > global > ordem original de order_index), persistência via
API, e as telas admin/pessoal de padrão global.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.permission import Permission
from model.core.transaction import Transaction
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


def _admin_group_code(app) -> str:
    with app.app_context():
        return Transaction.query.filter_by(code="TX_GROUP_ADMIN").first().code


# ── Resolução de estado ──────────────────────────────────────────────────

def test_sem_nenhuma_preferencia_usa_dict_vazio(app):
    with app.app_context():
        state = svc.resolve_menu_state(None)
        assert state["order_overrides"] == {}
        assert state["collapsed_nodes"] == set()
        assert state["sidebar_collapsed"] is False


def test_padrao_global_e_aplicado(app):
    with app.app_context():
        svc.set_global_defaults(
            order_overrides={"__root__": ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO", "TX_GROUP_ADMIN"]},
            collapsed_nodes=["TX_GROUP_ADMIN"],
            default_sidebar_collapsed=True,
        )
        state = svc.resolve_menu_state(None)
        assert state["order_overrides"]["__root__"] == ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO", "TX_GROUP_ADMIN"]
        assert state["collapsed_nodes"] == {"TX_GROUP_ADMIN"}
        assert state["sidebar_collapsed"] is True


def test_override_do_usuario_sobrepoe_padrao_global(app):
    with app.app_context():
        user = User(username="menu_user", email="menu_user@test.local", nome="Menu",
                    nome_completo="Menu User", celular="0", is_active=True)
        user.set_password("x")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        svc.set_global_defaults(default_sidebar_collapsed=True)
        svc.save_user_preference(
            user_id,
            order_overrides={"__root__": ["TX_GROUP_ADMIN"]},
            sidebar_collapsed=False,
        )

        state = svc.resolve_menu_state(user_id)
        assert state["order_overrides"]["__root__"] == ["TX_GROUP_ADMIN"]
        assert state["sidebar_collapsed"] is False  # override do usuário venceu


# ── Construção da árvore (pages.py) ──────────────────────────────────────

def test_arvore_da_home_aplica_order_overrides(app, client):
    with app.app_context():
        svc.set_global_defaults(order_overrides={
            "__root__": ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO", "TX_GROUP_ADMIN"],
        })
    _login_admin(app, client)
    resp = client.get("/")
    body = resp.data.decode()
    # "Ferramentas de Desenvolvimento" deve aparecer ANTES de "Admin" no HTML.
    assert body.index("Ferramentas de Desenvolvimento") < body.index('bi-gear-fill"></i> Admin</h5>')


def test_grupo_core_nunca_aparece_no_menu(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    body = resp.data.decode()
    # TX_HOME (filho de TX_GROUP_CORE) some no menu porque o próprio
    # grupo Core é pulado — mas a rota / continua acessível via link fixo.
    assert ">Core<" not in body


# ── API de preferência do usuário ───────────────────────────────────────

def test_salvar_preferencia_via_api(app, client):
    user_id = _login_admin(app, client)

    resp = client.post(
        "/api/menu-preference",
        json={"sidebar_collapsed": True, "collapsed_nodes": ["TX_GROUP_ADMIN"]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    with app.app_context():
        from model.core.user_menu_preference import UserMenuPreference
        pref = UserMenuPreference.query.filter_by(user_id=user_id).first()
        assert pref.sidebar_collapsed is True
        assert pref.collapsed_nodes_json == ["TX_GROUP_ADMIN"]


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
    import json
    resp = client.post(
        "/admin/menu-settings/",
        data={
            "order_overrides_json": json.dumps({"__root__": ["TX_GROUP_ADMIN", "TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO"]}),
            "collapsed_nodes_json": json.dumps(["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO"]),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert svc.get_global_order_overrides()["__root__"] == ["TX_GROUP_ADMIN", "TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO"]
        assert svc.get_global_collapsed_nodes() == ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO"]
        assert svc.get_global_default_sidebar_collapsed() is False


def test_salvar_padrao_global_com_json_invalido_falha_sem_quebrar(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/menu-settings/",
        data={"order_overrides_json": "{invalido"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "invalido".encode() not in resp.data or b"inv\xc3\xa1lidos" in resp.data


# ── Tela pessoal de preferências (perfil) ───────────────────────────────

def test_tela_pessoal_de_menu_carrega_para_qualquer_usuario_logado(app, client):
    with app.app_context():
        user = User(username="usuario_comum", email="uc@test.local", nome="Comum",
                     nome_completo="Usuario Comum", celular="0", is_active=True, is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "usuario_comum", "password": "x"})

    resp = client.get("/perfil/menu-preferencias")
    assert resp.status_code == 200
    assert b"Minhas Prefer\xc3\xaancias de Menu" in resp.data


def test_salvar_preferencia_pessoal_via_form_nao_afeta_padrao_global(app, client):
    with app.app_context():
        user = User(username="usuario_menu", email="um@test.local", nome="Menu",
                     nome_completo="Usuario Menu", celular="0", is_active=True, is_admin=False)
        user.set_password("x")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    client.post("/api/auth/login", json={"username": "usuario_menu", "password": "x"})

    with app.app_context():
        svc.set_global_defaults(order_overrides={"__root__": ["TX_GROUP_ADMIN"]})

    import json
    resp = client.post(
        "/perfil/menu-preferencias",
        data={"order_overrides_json": json.dumps({"__root__": ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO", "TX_GROUP_ADMIN"]})},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        from model.core.user_menu_preference import UserMenuPreference
        pref = UserMenuPreference.query.filter_by(user_id=user_id).first()
        assert pref.order_overrides_json["__root__"] == ["TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO", "TX_GROUP_ADMIN"]
        # Padrão global não foi tocado pelo salvamento pessoal.
        assert svc.get_global_order_overrides()["__root__"] == ["TX_GROUP_ADMIN"]


# ── Permissão fixa seedada no boot ──────────────────────────────────────

def test_permissao_menu_settings_seedada_no_boot(app):
    with app.app_context():
        assert Permission.query.filter_by(name="system_config.menu_settings").first() is not None
