"""
tests/test_ui_navigation_fixes.py

Cobre os bugs reais de UI/UX corrigidos numa rodada de feedback:
toggle do sidebar (web.js nunca era incluído), tema escuro (seletor
CSS não batia com a classe aplicada), submenus colapsáveis, e a tela
de gestão de Transações (criar manual, editar, bloqueio de edição de
transação vinda do código).
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
        admin = User(
            username="admin", email="admin@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=True, is_active=True,
        )
        admin.set_password("senha123")
        db.session.add(admin)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


# ── Toggle do sidebar (web.js nunca era incluído) ───────────────────────────

def test_web_js_incluido_na_pagina(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    assert b'src="/static/js/web.js"' in resp.data


def test_web_js_tem_o_handler_do_toggle_sidebar():
    with open("static/js/web.js", encoding="utf-8") as f:
        content = f.read()
    assert "toggle-sidebar-btn" in content
    assert "toggle-sidebar" in content


def test_web_js_protege_tinymce_init_contra_biblioteca_ausente():
    """
    tinymce.init() era chamado sem guarda — quebrava o resto do script
    (incluindo a inicialização de DataTables) em qualquer página sem
    o TinyMCE carregado.
    """
    with open("static/js/web.js", encoding="utf-8") as f:
        content = f.read()
    assert "typeof tinymce !== 'undefined'" in content


# ── Tema escuro (seletor CSS não batia com a classe aplicada) ──────────────

def test_tema_claro_nao_carrega_css_escuro(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    assert b'data-theme="light"' in resp.data
    assert b'href="/static/css/style_dark.css"' not in resp.data


def test_tema_escuro_usa_data_theme_correto(app, client):
    """
    style_dark.css usa majoritariamente o seletor `html[data-theme="dark"]`
    (129 ocorrências) — a classe antiga `body.theme-dark` nunca batia
    com nenhuma regra real do CSS.
    """
    _login_admin(app, client)
    client.post("/api/auth/update-theme", json={"theme": "dark"})

    resp = client.get("/")
    assert b'data-theme="dark"' in resp.data
    assert b'href="/static/css/style_dark.css"' in resp.data


def test_meta_color_scheme_trava_modo_do_navegador(app, client):
    """
    Sem isso, o navegador pode forçar dark mode por fora do nosso
    controle (forced dark do Chrome/Android), criando inconsistência
    visual independente do nosso próprio toggle.
    """
    _login_admin(app, client)
    resp = client.get("/")
    assert b'name="color-scheme" content="light"' in resp.data

    client.post("/api/auth/update-theme", json={"theme": "dark"})
    resp = client.get("/")
    assert b'name="color-scheme" content="dark"' in resp.data


def test_text_muted_tem_cobertura_no_css_escuro():
    """.text-muted usava o cinza padrão do Bootstrap, ilegível no fundo escuro."""
    with open("static/css/style_dark.css", encoding="utf-8") as f:
        content = f.read()
    assert ".text-muted" in content


# ── Submenus colapsáveis ─────────────────────────────────────────────────────

def test_sidebar_usa_submenus_colapsaveis_nativos_do_nice_admin(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    assert b"nav-content" in resp.data
    assert b'data-bs-toggle="collapse"' in resp.data
    assert b"bi-chevron-down" in resp.data


# ── Gestão de Transações ────────────────────────────────────────────────────

def test_tela_de_transacoes_abre(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/transactions/")
    assert resp.status_code == 200


def test_criar_transacao_manual(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/transactions/",
        data={"code": "TX_TESTE_MANUAL", "label": "Teste", "route": "/algo", "group": "Extras"},
        follow_redirects=True,
    )
    assert "criada".encode() in resp.data

    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_TESTE_MANUAL").first()
        assert tx is not None
        assert tx.source_module == "manual"
        assert tx.is_standard is False


def test_nao_permite_codigo_duplicado(app, client):
    _login_admin(app, client)
    client.post("/admin/transactions/", data={"code": "TX_DUP", "label": "A", "route": "/a"})
    resp = client.post(
        "/admin/transactions/", data={"code": "TX_DUP", "label": "B", "route": "/b"}, follow_redirects=True,
    )
    assert "Já existe".encode() in resp.data


def test_editar_transacao_manual(app, client):
    _login_admin(app, client)
    client.post("/admin/transactions/", data={"code": "TX_EDIT", "label": "Original", "route": "/x"})
    with app.app_context():
        tx_id = Transaction.query.filter_by(code="TX_EDIT").first().id

    resp = client.post(
        f"/admin/transactions/{tx_id}",
        data={"label": "Editado", "route": "/y", "group": "Novo Grupo"},
        follow_redirects=True,
    )
    assert "atualizada".encode() in resp.data

    with app.app_context():
        tx = Transaction.query.get(tx_id)
        assert tx.label == "Editado"
        assert tx.route == "/y"


def test_bloqueia_edicao_de_transacao_vinda_do_codigo(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx_id = Transaction.query.filter_by(code="TX_ADMIN_USERS").first().id

    resp = client.post(
        f"/admin/transactions/{tx_id}", data={"label": "Hackeado", "route": "/x"}, follow_redirects=True,
    )
    assert "vem do código".encode() in resp.data

    with app.app_context():
        tx = Transaction.query.get(tx_id)
        assert tx.label != "Hackeado"


def test_bloqueia_exclusao_de_transacao_vinda_do_codigo(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx_id = Transaction.query.filter_by(code="TX_ADMIN_USERS").first().id

    resp = client.post(f"/admin/transactions/{tx_id}/delete", follow_redirects=True)
    assert "desative em vez de excluir".encode() in resp.data

    with app.app_context():
        assert Transaction.query.get(tx_id) is not None


def test_permite_ativar_desativar_transacao_vinda_do_codigo(app, client):
    _login_admin(app, client)
    with app.app_context():
        tx_id = Transaction.query.filter_by(code="TX_ADMIN_USERS").first().id

    client.post(f"/admin/transactions/{tx_id}/toggle")
    with app.app_context():
        assert Transaction.query.get(tx_id).is_active is False


def test_remove_transacao_manual(app, client):
    _login_admin(app, client)
    client.post("/admin/transactions/", data={"code": "TX_DEL", "label": "A", "route": "/a"})
    with app.app_context():
        tx_id = Transaction.query.filter_by(code="TX_DEL").first().id

    client.post(f"/admin/transactions/{tx_id}/delete")

    with app.app_context():
        assert Transaction.query.get(tx_id) is None
