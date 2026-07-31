"""
tests/test_fase10_patch3_motor_de_acoes.py

Fase 10, Patch 3 — core/actions_catalog.py, DesignerComponent.events
finalmente ganhando escrita real via update_component, e o único
endpoint server-side do motor de Ações
(/admin/designer/data-action/<id>/execute).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent
from model.core.designer_data_action import DesignerDataAction
from model.core.odata_connection import ODataConnection
from core.actions_catalog import ACTION_CATALOG, get_action_def, get_server_action_ids
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain


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


def _create_page_with_button(client):
    client.post("/admin/designer/", data={"name": "Painel de Ações"})
    with client.application.app_context():
        page_id = DesignerPage.query.filter_by(name="Painel de Ações").first().id
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "button"})
    comp_id = resp.get_json()["component"]["id"]
    return page_id, comp_id


def _local_data_action(app, operation="query"):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(
            name=f"Ação {operation}", connection_id=local_conn.id,
            entity_name="yeast_strain", operation=operation,
        )
        db.session.add(action)
        db.session.commit()
        return action.id


# ── core/actions_catalog.py ─────────────────────────────────────────────

def test_catalogo_tem_as_5_acoes_decididas():
    ids = [a["id"] for a in ACTION_CATALOG]
    assert set(ids) == {"navigate", "show_message", "set_component_value", "toggle_component", "call_data_action"}


def test_get_action_def_existente():
    d = get_action_def("navigate")
    assert d is not None
    assert d["runs_on"] == "client"


def test_get_action_def_inexistente():
    assert get_action_def("nao_existe") is None


def test_apenas_call_data_action_roda_no_servidor():
    assert get_server_action_ids() == ["call_data_action"]


# ── update_component aceita events ──────────────────────────────────────

def test_update_component_salva_events_validos(app, client):
    _login_admin(app, client)
    _, comp_id = _create_page_with_button(client)

    events = {"onClick": [{"action_type": "show_message", "params": {"message": "Oi", "variant": "info"}}]}
    resp = client.post(f"/admin/designer/component/{comp_id}", json={"events": events})
    assert resp.status_code == 200
    assert resp.get_json()["component"]["events"] == events

    with app.app_context():
        assert DesignerComponent.query.get(comp_id).events == events


def test_update_component_evento_invalido_rejeitado(app, client):
    _login_admin(app, client)
    _, comp_id = _create_page_with_button(client)

    resp = client.post(f"/admin/designer/component/{comp_id}", json={"events": {"onSubmit": []}})
    assert resp.status_code == 422


def test_update_component_action_type_invalido_rejeitado(app, client):
    _login_admin(app, client)
    _, comp_id = _create_page_with_button(client)

    resp = client.post(
        f"/admin/designer/component/{comp_id}",
        json={"events": {"onClick": [{"action_type": "acao_que_nao_existe", "params": {}}]}},
    )
    assert resp.status_code == 422


# ── /admin/designer/data-action/<id>/execute ─────────────────────────────

def test_execute_data_action_query_retorna_dados_reais(app, client):
    with app.app_context():
        db.session.add(YeastStrain(name="Executada via Ação", status="disponivel"))
        db.session.commit()
    action_id = _local_data_action(app, operation="query")
    _login_admin(app, client)

    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert any(r["name"] == "Executada via Ação" for r in data["result"]["value"])


def test_execute_data_action_update_altera_registro(app, client):
    with app.app_context():
        strain = YeastStrain(name="Antes", status="disponivel")
        db.session.add(strain)
        db.session.commit()
        strain_id = strain.id
    action_id = _local_data_action(app, operation="update")
    _login_admin(app, client)

    resp = client.post(
        f"/admin/designer/data-action/{action_id}/execute",
        json={"key": str(strain_id), "payload": {"name": "Depois"}},
    )
    assert resp.status_code == 200
    with app.app_context():
        assert YeastStrain.query.get(strain_id).name == "Depois"


def test_execute_data_action_update_sem_key_falha(app, client):
    action_id = _local_data_action(app, operation="update")
    _login_admin(app, client)

    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={"payload": {"name": "X"}})
    assert resp.status_code == 422


def test_execute_data_action_inexistente_404(app, client):
    _login_admin(app, client)
    resp = client.post("/admin/designer/data-action/999999/execute", json={})
    assert resp.status_code == 404


def test_execute_data_action_operation_create_501(app, client):
    action_id = _local_data_action(app, operation="create")
    _login_admin(app, client)
    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={})
    assert resp.status_code == 501


def test_execute_data_action_exige_login(app, client):
    action_id = _local_data_action(app, operation="query")
    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={})
    assert resp.status_code in (302, 401)


def test_execute_data_action_respeita_permission_required(app, client):
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(
            name="Ação restrita", connection_id=local_conn.id,
            entity_name="yeast_strain", operation="query",
            permission_required="permissao_que_ninguem_tem",
        )
        db.session.add(action)
        db.session.commit()
        action_id = action.id

        user = User(
            username="semrole", email="s@test.local", nome="S", nome_completo="Sem Role",
            celular="119", is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()

    client.post("/api/auth/login", json={"username": "semrole", "password": "senha123"})
    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={})
    assert resp.status_code == 403


# ── editor renderiza o painel de eventos ─────────────────────────────────

def test_editor_recebe_catalogo_de_acoes_e_data_actions(app, client):
    _login_admin(app, client)
    page_id, _ = _create_page_with_button(client)
    _local_data_action(app, operation="query")

    resp = client.get(f"/admin/designer/{page_id}/edit")
    assert resp.status_code == 200
    assert b"ACTION_CATALOG" in resp.data
    assert b"call_data_action" in resp.data


# ── runtime injeta data-events no botão ──────────────────────────────────

def test_runtime_botao_com_events_recebe_data_events(app, client):
    _login_admin(app, client)
    page_id, comp_id = _create_page_with_button(client)
    events = {"onClick": [{"action_type": "navigate", "params": {"url": "/destino"}}]}
    client.post(f"/admin/designer/component/{comp_id}", json={"events": events})

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    resp = client.get(f"/designer/{slug}")
    assert resp.status_code == 200
    assert b"data-events=" in resp.data
    assert b"/destino" in resp.data
