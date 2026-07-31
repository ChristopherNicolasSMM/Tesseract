"""
tests/test_fase10_patch6_substituicao_menu.py

Fase 10, Patch 6 — core/designer_menu_override.py: o checkbox
DesignerPage.replace_in_menu (schema desde o Patch 1) finalmente
troca de fato o item de menu (Transaction.route) de uma tela do
CrudGen pela DesignerPage publicada. Usa TX_YEAST_BANK
("/brewstation/yeast-strains", permission_required="yeast_strains.list")
como entidade real de prova.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.transaction import Transaction
from core.designer_menu_override import resolve_designer_page_menu_overrides

_ORIGINAL_ROUTE = "/brewstation/yeast-strains"
_ENTITY_KEY = "yeast_strains"


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


def _create_page(client, name="Tela Custom Cepas"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


def _route_of(app, entity_key=_ENTITY_KEY):
    with app.app_context():
        tx = Transaction.query.filter_by(permission_required=f"{entity_key}.list").first()
        return tx.route if tx else None


# ── baseline ──────────────────────────────────────────────────────────

def test_rota_original_intacta_sem_nenhuma_designer_page(app):
    assert _route_of(app) == _ORIGINAL_ROUTE


# ── resolver direto ───────────────────────────────────────────────────

def test_resolver_troca_rota_quando_publicada_e_replace_in_menu(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        page.replace_in_menu = True
        page.replaces_entity_key = _ENTITY_KEY
        page.replaces_view = "manage"
        db.session.commit()
        slug = page.slug

        resolve_designer_page_menu_overrides()

    assert _route_of(app) == f"/designer/{slug}"


def test_resolver_nao_troca_se_nao_publicada(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = False
        page.replace_in_menu = True
        page.replaces_entity_key = _ENTITY_KEY
        page.replaces_view = "manage"
        db.session.commit()

        resolve_designer_page_menu_overrides()

    assert _route_of(app) == _ORIGINAL_ROUTE


def test_resolver_nao_troca_se_replaces_view_detail(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        page.replace_in_menu = True
        page.replaces_entity_key = _ENTITY_KEY
        page.replaces_view = "detail"
        db.session.commit()

        resolve_designer_page_menu_overrides()

    assert _route_of(app) == _ORIGINAL_ROUTE


def test_resolver_desmarcar_checkbox_restaura_rota_original(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        page.replace_in_menu = True
        page.replaces_entity_key = _ENTITY_KEY
        page.replaces_view = "manage"
        db.session.commit()
        resolve_designer_page_menu_overrides()
    assert _route_of(app) == f"/designer/{_slug(app, page_id)}"

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.replace_in_menu = False
        db.session.commit()
        resolve_designer_page_menu_overrides()

    assert _route_of(app) == _ORIGINAL_ROUTE


def _slug(app, page_id):
    with app.app_context():
        return DesignerPage.query.get(page_id).slug


def test_resolver_apagar_pagina_restaura_rota_original(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        page.replace_in_menu = True
        page.replaces_entity_key = _ENTITY_KEY
        page.replaces_view = "manage"
        db.session.commit()
        resolve_designer_page_menu_overrides()
        db.session.delete(DesignerPage.query.get(page_id))
        db.session.commit()
        resolve_designer_page_menu_overrides()

    assert _route_of(app) == _ORIGINAL_ROUTE


def test_resolver_entity_key_sem_transacao_correspondente_nao_quebra(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        page.replace_in_menu = True
        page.replaces_entity_key = "entidade_que_nao_existe"
        page.replaces_view = "manage"
        db.session.commit()

        resolve_designer_page_menu_overrides()  # não deve lançar exceção

    assert _route_of(app) == _ORIGINAL_ROUTE


# ── rotas HTTP ────────────────────────────────────────────────────────

def test_update_settings_salva_campos_e_aplica_resolver(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)

    resp = client.post(f"/admin/designer/{page_id}/settings", data={
        "permission_required": "",
        "replaces_entity_key": _ENTITY_KEY,
        "replaces_view": "manage",
        "replace_in_menu": "on",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        assert page.replaces_entity_key == _ENTITY_KEY
        assert page.replaces_view == "manage"
        assert page.replace_in_menu is True
        # ainda não publicada -> resolver não deve ter trocado a rota
        assert _route_of(app) == _ORIGINAL_ROUTE


def test_publish_com_replace_in_menu_troca_rota_via_http(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    client.post(f"/admin/designer/{page_id}/settings", data={
        "replaces_entity_key": _ENTITY_KEY,
        "replaces_view": "manage",
        "replace_in_menu": "on",
    })

    client.post(f"/admin/designer/{page_id}/publish")

    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug
    assert _route_of(app) == f"/designer/{slug}"

    # despublicar de novo -> restaura
    client.post(f"/admin/designer/{page_id}/publish")
    assert _route_of(app) == _ORIGINAL_ROUTE


def test_delete_com_replace_in_menu_restaura_rota_via_http(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    client.post(f"/admin/designer/{page_id}/settings", data={
        "replaces_entity_key": _ENTITY_KEY,
        "replaces_view": "manage",
        "replace_in_menu": "on",
    })
    client.post(f"/admin/designer/{page_id}/publish")
    assert _route_of(app) != _ORIGINAL_ROUTE

    client.post(f"/admin/designer/{page_id}/delete")
    assert _route_of(app) == _ORIGINAL_ROUTE
