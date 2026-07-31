"""
tests/test_fase10_patch5_tier2_componentes.py

Fase 10, Patch 5 — Tier 2 de componente do Designer
(mapeamento_niceadmin_designer.md): card, alert, badge, progress_bar,
list. Mais barato que o Tier 1 — nenhum exige bind obrigatório a
registro único; só `list` fala com uma Ação de Dado.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import COMPONENT_TYPES
from model.core.designer_data_action import DesignerDataAction
from model.core.odata_connection import ODataConnection


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


def _create_page(client, name="Painel Tier 2"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


def _publish(app, page_id):
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        return page.slug


def test_component_types_inclui_tier2():
    assert set(COMPONENT_TYPES) >= {"card", "alert", "badge", "progress_bar", "list"}


@pytest.mark.parametrize("comp_type,expected_w,expected_h", [
    ("card", 320, 220),
    ("alert", 400, 60),
    ("badge", 100, 30),
    ("progress_bar", 300, 30),
    ("list", 320, 260),
])
def test_novo_componente_usa_tamanho_padrao_do_tipo(app, client, comp_type, expected_w, expected_h):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": comp_type})
    comp = resp.get_json()["component"]
    assert comp["width"] == expected_w
    assert comp["height"] == expected_h


def test_progress_bar_default_properties(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "progress_bar"})
    props = resp.get_json()["component"]["properties"]
    assert props["value"] == 50
    assert props["min"] == 0
    assert props["max"] == 100


def test_runtime_card_renderiza_titulo_corpo_e_rodape(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "card"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"title": "Cepa Ale", "body_text": "Boa pra IPA", "footer_text": "Atualizado hoje"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"Cepa Ale" in resp.data
    assert b"Boa pra IPA" in resp.data
    assert b"Atualizado hoje" in resp.data
    assert b"card-body" in resp.data


def test_runtime_alert_usa_variante_configurada(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "alert"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"message": "Estoque baixo", "variant": "warning"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"alert-warning" in resp.data
    assert b"Estoque baixo" in resp.data


def test_runtime_badge_usa_texto_e_variante(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "badge"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"text": "Esgotado", "variant": "danger"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"bg-danger" in resp.data
    assert b"Esgotado" in resp.data


def test_runtime_progress_bar_calcula_percentual(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "progress_bar"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"value": 25, "min": 0, "max": 50, "variant": "success"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"width: 50.0%" in resp.data
    assert b"bg-success" in resp.data


def test_runtime_list_tem_atributos_de_bind(app, client):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(name="Listar Cepas", connection_id=local_conn.id, entity_name="yeast_strain")
        db.session.add(action)
        db.session.commit()
        action_id = action.id

    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "list"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"title": "Cepas Disponíveis", "data_action_id": str(action_id), "display_field": "name"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"data-list-comp" in resp.data
    assert f'data-data-action-id="{action_id}"'.encode() in resp.data
    assert b'data-display-field="name"' in resp.data
    assert b"Cepas Dispon" in resp.data
