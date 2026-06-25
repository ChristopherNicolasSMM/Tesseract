"""
tests/test_phase7c_designer.py

Cobre o Designer visual (Fase 7c): CRUD de páginas e componentes,
publicação/despublicação, controle de acesso da tela de execução, e
a conexão real com o motor de validação da Fase 7b (a peça que
ficava catalogada sem nenhum alvo até esta fase existir).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent


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


def _create_page(client, name="Painel de Teste"):
    resp = client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


# ── Páginas ──────────────────────────────────────────────────────────────────

def test_lista_de_paginas_abre(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/designer/")
    assert resp.status_code == 200


def test_criar_pagina_gera_slug_unico(app, client):
    _login_admin(app, client)
    client.post("/admin/designer/", data={"name": "Painel Teste"})
    client.post("/admin/designer/", data={"name": "Painel Teste"})

    with app.app_context():
        pages = DesignerPage.query.filter(DesignerPage.name == "Painel Teste").all()
        assert len(pages) == 2
        slugs = {p.slug for p in pages}
        assert len(slugs) == 2  # nunca colide


def test_excluir_pagina_remove_componentes_em_cascata(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    client.post(f"/admin/designer/{page_id}/components", json={"type": "heading"})

    client.post(f"/admin/designer/{page_id}/delete")

    with app.app_context():
        assert DesignerPage.query.get(page_id) is None
        assert DesignerComponent.query.filter_by(page_id=page_id).count() == 0


# ── Componentes ──────────────────────────────────────────────────────────────

def test_adicionar_componente_usa_tamanho_padrao_do_tipo(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)

    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "button"})
    comp = resp.get_json()["component"]
    assert comp["width"] == 140
    assert comp["height"] == 40


def test_adicionar_componente_tipo_invalido_falha(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)

    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "datagrid_que_nao_existe"})
    assert resp.status_code == 422


def test_atualizar_posicao_e_tamanho(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    comp = client.post(f"/admin/designer/{page_id}/components", json={"type": "label"}).get_json()["component"]

    resp = client.post(f"/admin/designer/component/{comp['id']}", json={"x": 300, "y": 150, "width": 250, "height": 80})
    updated = resp.get_json()["component"]
    assert updated["x"] == 300
    assert updated["y"] == 150
    assert updated["width"] == 250
    assert updated["height"] == 80


def test_atualizar_propriedades(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    comp = client.post(f"/admin/designer/{page_id}/components", json={"type": "heading"}).get_json()["component"]

    resp = client.post(f"/admin/designer/component/{comp['id']}", json={"properties": {"text": "Olá Mundo"}})
    assert resp.get_json()["component"]["properties"]["text"] == "Olá Mundo"


def test_excluir_componente(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    comp = client.post(f"/admin/designer/{page_id}/components", json={"type": "label"}).get_json()["component"]

    client.post(f"/admin/designer/component/{comp['id']}/delete")

    with app.app_context():
        assert DesignerComponent.query.get(comp["id"]) is None


# ── Publicação e execução ───────────────────────────────────────────────────

def test_pagina_nao_publicada_retorna_404(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug

    resp = client.get(f"/designer/{slug}")
    assert resp.status_code == 404


def test_publicar_e_acessar_pagina(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    client.post(f"/admin/designer/{page_id}/components", json={"type": "heading"})
    comp_id = DesignerComponent.query.first().id if False else None  # noqa

    with app.app_context():
        comp = DesignerComponent.query.filter_by(page_id=page_id).first()
        comp.properties = {"text": "Painel Publicado"}
        db.session.commit()
        slug = DesignerPage.query.get(page_id).slug

    client.post(f"/admin/designer/{page_id}/publish")

    resp = client.get(f"/designer/{slug}")
    assert resp.status_code == 200
    assert b"Painel Publicado" in resp.data


def test_despublicar_volta_a_dar_404(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug

    client.post(f"/admin/designer/{page_id}/publish")
    assert client.get(f"/designer/{slug}").status_code == 200

    client.post(f"/admin/designer/{page_id}/publish")
    assert client.get(f"/designer/{slug}").status_code == 404


def test_pagina_com_permissao_bloqueia_usuario_sem_permissao(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.permission_required = "admin"
        db.session.commit()
        slug = page.slug
    client.post(f"/admin/designer/{page_id}/publish")

    client.post("/api/auth/logout")
    with app.app_context():
        comum = User(
            username="comum", email="comum@test.local",
            nome="Comum", nome_completo="Usuario Comum", celular="11988888888",
            is_admin=False, is_active=True,
        )
        comum.set_password("senha123")
        db.session.add(comum)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "comum", "password": "senha123"})

    resp = client.get(f"/designer/{slug}")
    assert resp.status_code == 403


# ── Conexão real com o motor de validação (Fase 7b) ─────────────────────────

def test_regra_de_validacao_anexada_aparece_renderizada(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    comp = client.post(f"/admin/designer/{page_id}/components", json={"type": "textbox"}).get_json()["component"]

    client.post(
        f"/admin/designer/component/{comp['id']}",
        json={
            "properties": {"label": "Nome", "field_name": "nome"},
            "rules": [{"js_function": "required", "params": {"message": "Obrigatório!"}}],
        },
    )

    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug
    client.post(f"/admin/designer/{page_id}/publish")

    resp = client.get(f"/designer/{slug}")
    assert b"data-rules=" in resp.data
    assert b"required" in resp.data
    assert b"rule_engine.js" in resp.data


def test_textbox_sem_regra_nao_recebe_data_rules(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    client.post(f"/admin/designer/{page_id}/components", json={"type": "textbox"})

    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug
    client.post(f"/admin/designer/{page_id}/publish")

    resp = client.get(f"/designer/{slug}")
    assert b"data-rules=" not in resp.data
