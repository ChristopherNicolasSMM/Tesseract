"""
tests/test_fase10_patch4_tier1_componentes.py

Fase 10, Patch 4 — Tier 1 de componente do Designer
(mapeamento_niceadmin_designer.md): select, checkbox, radio,
form_container, datagrid. Cobre criação com tamanho/propriedades
padrão corretos e renderização no runtime com os atributos data-*
que static/js/data_binding.js consome (não há execução de JS nos
testes — mesmo padrão já usado para data-rules/data-events).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent, COMPONENT_TYPES
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


def _create_page(client, name="Painel Tier 1"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


def _publish(app, page_id):
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        return page.slug


# ── catálogo de tipos ──────────────────────────────────────────────────

def test_component_types_inclui_tier1():
    assert set(COMPONENT_TYPES) >= {"select", "checkbox", "radio", "form_container", "datagrid"}


# ── criação com defaults corretos ───────────────────────────────────────

@pytest.mark.parametrize("comp_type,expected_w,expected_h", [
    ("select", 280, 60),
    ("checkbox", 220, 30),
    ("radio", 280, 100),
    ("form_container", 420, 320),
    ("datagrid", 600, 320),
])
def test_novo_componente_usa_tamanho_padrao_do_tipo(app, client, comp_type, expected_w, expected_h):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": comp_type})
    comp = resp.get_json()["component"]
    assert comp["width"] == expected_w
    assert comp["height"] == expected_h


def test_select_default_properties(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "select"})
    props = resp.get_json()["component"]["properties"]
    assert props["options_source"] == "static"
    assert props["value_field"] == "id"
    assert props["label_field"] == "name"


def test_form_container_default_properties(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "form_container"})
    props = resp.get_json()["component"]["properties"]
    assert props["key_param"] == "id"
    # Fase 11, Patch 1: data_action_id passou a ser tipado (int | None)
    # via schema do catálogo — antes era string vazia, como tudo mais.
    assert props["data_action_id"] is None


def test_datagrid_default_properties(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "datagrid"})
    props = resp.get_json()["component"]["properties"]
    assert props["columns"] == ""
    assert props["data_action_id"] is None


# ── runtime: atributos data-* consumidos por data_binding.js ────────────

def test_runtime_select_estatico_tem_atributos_corretos(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "select"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"label": "Status", "field_name": "status", "options_source": "static", "static_options": "A,B,C"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"data-select-comp" in resp.data
    assert b'data-options-source="static"' in resp.data
    assert b'data-static-options="A,B,C"' in resp.data
    assert b'name="status"' in resp.data


def test_runtime_select_dinamico_tem_data_action_id(app, client):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(name="Listar Y", connection_id=local_conn.id, entity_name="yeast_strain")
        db.session.add(action)
        db.session.commit()
        action_id = action.id

    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "select"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"options_source": "data_action", "data_action_id": str(action_id), "value_field": "id", "label_field": "name"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert f'data-data-action-id="{action_id}"'.encode() in resp.data
    assert b'data-options-source="data_action"' in resp.data


def test_runtime_checkbox_marcado_por_padrao(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "checkbox"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"label": "Ativo", "field_name": "ativo", "checked_default": "true"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b'type="checkbox"' in resp.data
    assert b"checked" in resp.data


def test_runtime_radio_tem_atributos_de_opcoes(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "radio"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"field_name": "prioridade", "options": "Baixa,Média,Alta", "default_value": "Média"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"data-radio-group" in resp.data
    assert b'data-radio-name="prioridade"' in resp.data
    assert b'data-radio-options="Baixa,M' in resp.data
    assert b'data-radio-default="M' in resp.data


def test_runtime_form_container_tem_geometria_e_data_action(app, client):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(name="Buscar Y", connection_id=local_conn.id, entity_name="yeast_strain")
        db.session.add(action)
        db.session.commit()
        action_id = action.id

    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "form_container"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"title": "Editar Cepa", "data_action_id": str(action_id), "key_param": "id"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"data-form-container" in resp.data
    assert f'data-data-action-id="{action_id}"'.encode() in resp.data
    assert b'data-key-param="id"' in resp.data
    assert b"Editar Cepa" in resp.data


def test_runtime_datagrid_tem_tabela_e_data_action(app, client):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(name="Listar Z", connection_id=local_conn.id, entity_name="yeast_strain")
        db.session.add(action)
        db.session.commit()
        action_id = action.id

    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "datagrid"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"title": "Cepas", "data_action_id": str(action_id), "columns": "name,status"},
    })
    slug = _publish(app, page_id)

    resp = client.get(f"/designer/{slug}")
    assert b"data-datagrid" in resp.data
    assert b"data-datagrid-table" in resp.data
    assert f'data-data-action-id="{action_id}"'.encode() in resp.data
    assert b'data-columns="name,status"' in resp.data


def test_runtime_carrega_data_binding_js(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    slug = _publish(app, page_id)
    resp = client.get(f"/designer/{slug}")
    assert b"js/data_binding.js" in resp.data
