"""
tests/test_fase11_patch1_catalogo_componentes.py

Fase 11, Patch 1 — core/components_catalog.py: schema de propriedade
declarado por TIPO (equivalente a "trait" do GrapesJS / "field" do
Puck), substituindo a reflexão sobre as chaves salvas na instância.
Cobre principalmente a **preservação de tipo** (bool/int/None), que
era o defeito de fundo: tudo virava string vinda do <input>.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent, COMPONENT_TYPES
from model.core.designer_data_action import DesignerDataAction
from model.core.odata_connection import ODataConnection
from core.components_catalog import (
    COMPONENT_CATALOG, PROP_TYPES, CATEGORIES,
    get_component_def, get_component_types, get_default_size,
    get_default_properties, coerce_properties, accepts_children,
)


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


def _create_page(client, name="Página Schema"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


# ── integridade do catálogo ──────────────────────────────────────────

def test_catalogo_cobre_todos_os_tipos_do_model():
    assert set(get_component_types()) == set(COMPONENT_TYPES)


def test_todo_componente_tem_campos_obrigatorios():
    for comp in COMPONENT_CATALOG:
        assert comp["id"] and comp["label"] and comp["icon"]
        assert comp["category"] in [c[0] for c in CATEGORIES]
        assert isinstance(comp["accepts_children"], bool)
        assert len(comp["default_size"]) == 2


def test_toda_propriedade_tem_schema_valido():
    for comp in COMPONENT_CATALOG:
        for prop in comp["props"]:
            assert prop["name"], comp["id"]
            assert prop["label"], f'{comp["id"]}.{prop["name"]}'
            assert prop["type"] in PROP_TYPES, f'{comp["id"]}.{prop["name"]}'
            assert "default" in prop, f'{comp["id"]}.{prop["name"]}'
            if prop["type"] == "select":
                assert prop.get("options"), f'{comp["id"]}.{prop["name"]}'


def test_nome_de_propriedade_unico_dentro_do_tipo():
    for comp in COMPONENT_CATALOG:
        names = [p["name"] for p in comp["props"]]
        assert len(names) == len(set(names)), comp["id"]


def test_default_de_bool_e_number_tem_tipo_certo():
    """O ponto central do patch: o default nasce tipado no schema, não
    como string."""
    for comp in COMPONENT_CATALOG:
        for prop in comp["props"]:
            if prop["type"] == "bool":
                assert isinstance(prop["default"], bool), f'{comp["id"]}.{prop["name"]}'
            if prop["type"] == "number":
                assert isinstance(prop["default"], int), f'{comp["id"]}.{prop["name"]}'


def test_containers_declarados():
    assert accepts_children("form_container") is True
    assert accepts_children("card") is True
    assert accepts_children("button") is False


def test_get_component_def_inexistente():
    assert get_component_def("nao_existe") is None


def test_get_default_size_conhecido_e_desconhecido():
    assert get_default_size("datagrid") == (600, 320)
    assert get_default_size("nao_existe") == (150, 40)


# ── coerção de tipo ──────────────────────────────────────────────────

def test_coerce_bool_a_partir_de_string_de_checkbox():
    result = coerce_properties("heading", {"bold": "on"})
    assert result["bold"] is True

    result = coerce_properties("heading", {"bold": "false"})
    assert result["bold"] is False


def test_coerce_number_a_partir_de_string():
    result = coerce_properties("heading", {"font_size": "30"})
    assert result["font_size"] == 30
    assert isinstance(result["font_size"], int)


def test_coerce_number_invalido_cai_no_default():
    result = coerce_properties("heading", {"font_size": "abc"})
    assert result["font_size"] == 26


def test_coerce_data_action_vazio_vira_none():
    result = coerce_properties("select", {"data_action_id": ""})
    assert result["data_action_id"] is None


def test_coerce_data_action_string_vira_int():
    result = coerce_properties("select", {"data_action_id": "7"})
    assert result["data_action_id"] == 7


def test_coerce_completa_propriedade_ausente_com_default():
    result = coerce_properties("button", {"text": "Salvar"})
    assert result["text"] == "Salvar"
    assert result["variant"] == "primary"
    assert result["outline"] is False


def test_coerce_descarta_chave_que_nao_existe_no_tipo():
    result = coerce_properties("button", {"text": "X", "chave_inventada": "lixo"})
    assert "chave_inventada" not in result


def test_coerce_tipo_desconhecido_passa_direto():
    result = coerce_properties("nao_existe", {"qualquer": "coisa"})
    assert result == {"qualquer": "coisa"}


# ── integração com o controller ──────────────────────────────────────

def test_novo_componente_nasce_com_defaults_tipados(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "heading"})
    props = resp.get_json()["component"]["properties"]
    assert props["bold"] is True
    assert props["font_size"] == 26
    assert isinstance(props["font_size"], int)


def test_update_preserva_tipo_ao_salvar(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "progress_bar"})
    comp_id = resp.get_json()["component"]["id"]

    # o editor manda string/bool crus, como o formulário produz
    resp = client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"value": "75", "min": "0", "max": "100",
                       "variant": "success", "label_visible": True},
    })
    props = resp.get_json()["component"]["properties"]
    assert props["value"] == 75
    assert isinstance(props["value"], int)
    assert props["label_visible"] is True

    with app.app_context():
        saved = DesignerComponent.query.get(comp_id).properties
        assert saved["value"] == 75
        assert saved["label_visible"] is True


def test_runtime_usa_booleano_real_nao_string(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "checkbox"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"label": "Ativo", "checked_default": True, "style": "switch"},
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    resp = client.get(f"/designer/{slug}")
    assert b"checked" in resp.data
    assert b"form-switch" in resp.data


def test_runtime_honra_props_novas_do_botao(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "button"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"text": "Salvar", "variant": "success", "icon": "bi-save", "outline": True},
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    resp = client.get(f"/designer/{slug}")
    assert b"btn-outline-success" in resp.data
    assert b"bi-save" in resp.data


def test_runtime_honra_input_type_do_textbox(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.post(f"/admin/designer/{page_id}/components", json={"type": "textbox"})
    comp_id = resp.get_json()["component"]["id"]
    client.post(f"/admin/designer/component/{comp_id}", json={
        "properties": {"label": "E-mail", "field_name": "email", "input_type": "email"},
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    resp = client.get(f"/designer/{slug}")
    assert b'type="email"' in resp.data


def test_editor_recebe_catalogo_de_componentes(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.get(f"/admin/designer/{page_id}/edit")
    assert resp.status_code == 200
    assert b"COMPONENT_CATALOG" in resp.data
    # paleta agrupada por categoria, com label PT-BR (não o id cru)
    assert "Formulário".encode() in resp.data
    assert "Menu suspenso".encode() in resp.data


# ── Patch 1.1 — correções vistas no editor real ──────────────────────

def test_canvas_usa_variaveis_de_tema_nao_cor_hardcoded(app, client):
    """Fase 11, Patch 1.1: o canvas usava page.canvas_bg (default claro)
    e grid hardcoded claro, virando uma folha branca dentro do app
    escuro. Agora segue as variáveis semânticas de themes.css."""
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.get(f"/admin/designer/{page_id}/edit")
    assert b"var(--bg-secondary" in resp.data
    assert b"#f6f9ff;" not in resp.data.split(b"#designerCanvas")[1][:400]


def test_canvas_tem_wrapper_rolavel(app, client):
    """O canvas tem largura fixa em px; sem wrapper com max-width ele
    estourava a coluna e empurrava o painel de propriedades pra fora
    da tela."""
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.get(f"/admin/designer/{page_id}/edit")
    assert b"designerCanvasWrap" in resp.data
    assert b"max-width: 100%" in resp.data


def test_preview_do_editor_honra_estilo_do_label(app, client):
    """Regressão do Patch 1: o runtime honrava font_size/text_color/
    bold do label, mas o preview do canvas renderizava <span> puro, e
    o texto sumia herdando a cor do tema."""
    _login_admin(app, client)
    page_id = _create_page(client)
    resp = client.get(f"/admin/designer/{page_id}/edit")
    body = resp.data.decode()
    label_branch = body.split("comp.type === 'label'")[1][:400]
    assert "text_color" in label_branch
    assert "font_size" in label_branch
    assert "bold" in label_branch


def test_settings_persiste_dimensoes_do_canvas(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)

    client.post(f"/admin/designer/{page_id}/settings", data={
        "canvas_width": "900", "canvas_height": "600",
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        assert page.canvas_width == 900
        assert page.canvas_height == 600


def test_settings_dimensao_invalida_mantem_valor_atual(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)
    with app.app_context():
        original = DesignerPage.query.get(page_id).canvas_width

    client.post(f"/admin/designer/{page_id}/settings", data={"canvas_width": "abc"})
    with app.app_context():
        assert DesignerPage.query.get(page_id).canvas_width == original


def test_settings_dimensao_fora_da_faixa_e_limitada(app, client):
    _login_admin(app, client)
    page_id = _create_page(client)

    client.post(f"/admin/designer/{page_id}/settings", data={"canvas_width": "99999"})
    with app.app_context():
        assert DesignerPage.query.get(page_id).canvas_width == 4000
