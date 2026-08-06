"""
tests/test_fase12_paginas_customizadas.py

Fase 12 — o construtor visual do Designer foi removido; a página
customizada passa a ser HTML escrito à mão (`content_html`), servido
pelo runtime. Ver o docstring de model/core/designer_page.py.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.designer_page import DesignerPage
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


def _page(client, name="Painel Customizado"):
    client.post("/admin/designer/", data={"name": name})
    with client.application.app_context():
        return DesignerPage.query.filter_by(name=name).first().id


# ── o motor visual saiu ───────────────────────────────────────────────

def test_modulos_do_construtor_visual_nao_existem_mais():
    for modulo in ("core.components_catalog", "core.actions_catalog",
                   "model.core.designer_component"):
        with pytest.raises(ImportError):
            __import__(modulo)


def test_endpoints_de_componente_nao_existem_mais(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    assert client.post(f"/admin/designer/{page_id}/components", json={"type": "card"}).status_code == 404
    assert client.post("/admin/designer/component/1", json={}).status_code == 404
    assert client.post("/admin/designer/component/1/move-to", json={}).status_code == 404


# ── página customizada ────────────────────────────────────────────────

def test_pagina_nova_nasce_com_html_inicial(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    with app.app_context():
        page = DesignerPage.query.get(page_id)
    assert page.content_html
    assert "card-body" in page.content_html


def test_salvar_conteudo_html(app, client):
    _login_admin(app, client)
    page_id = _page(client)

    resp = client.post(f"/admin/designer/{page_id}/content", data={
        "title": "Meu Painel",
        "content_html": '<div class="alert alert-info">Olá</div>',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        page = DesignerPage.query.get(page_id)
        assert page.title == "Meu Painel"
        assert "alert-info" in page.content_html


def test_runtime_renderiza_html_da_pagina(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    client.post(f"/admin/designer/{page_id}/content", data={
        "content_html": '<div class="alert alert-warning">CONTEUDO PROPRIO</div>',
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    body = client.get(f"/designer/{slug}").data.decode()
    assert "CONTEUDO PROPRIO" in body
    # renderizado como HTML de verdade, não escapado
    assert "alert-warning" in body
    assert "&lt;div" not in body


def test_runtime_nao_interpreta_jinja_do_banco(app, client):
    """Renderizar Jinja vindo do banco seria SSTI — na prática execução
    de código no servidor, mesmo restrito a admin. O conteúdo é HTML
    confiável, nunca template."""
    _login_admin(app, client)
    page_id = _page(client)
    client.post(f"/admin/designer/{page_id}/content", data={
        "content_html": "<p>{{ 7 * 191 }}</p>",
    })
    with app.app_context():
        page = DesignerPage.query.get(page_id)
        page.is_published = True
        db.session.commit()
        slug = page.slug

    body = client.get(f"/designer/{slug}").data.decode()
    assert "1337" not in body
    assert "7 * 191" in body


def test_runtime_404_se_nao_publicada(app, client):
    _login_admin(app, client)
    page_id = _page(client)
    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug
    assert client.get(f"/designer/{slug}").status_code == 404


def test_editor_mostra_link_do_modelo_e_acoes_de_dado(app, client):
    with app.app_context():
        conn = ODataConnection.query.filter_by(is_local=True).first()
        db.session.add(DesignerDataAction(
            name="Listar Cepas", connection_id=conn.id, entity_name="yeast_strain",
        ))
        db.session.commit()

    _login_admin(app, client)
    page_id = _page(client)
    body = client.get(f"/admin/designer/{page_id}/edit").data.decode()
    assert "_modelo-pagina-basico.html" in body
    assert "_modelo-pagina-completo.html" in body
    assert "Listar Cepas" in body
    assert "data-action/" in body


@pytest.mark.parametrize("arquivo,marca", [
    ("_modelo-pagina-basico.html", "MODELO BÁSICO"),
    ("_modelo-pagina-completo.html", "MODELO COMPLETO"),
])
def test_modelos_de_pagina_sao_servidos(app, client, arquivo, marca):
    _login_admin(app, client)
    resp = client.get(f"/static/modelo_paginas_nice_admin/{arquivo}")
    assert resp.status_code == 200
    corpo = resp.data.decode("utf-8")
    assert marca in corpo
    assert "data-action" in corpo


def test_modelo_completo_cobre_os_tres_caminhos_de_dado(app, client):
    """O modelo completo é a referência viva da skill 17 — se um caminho
    sair dele, a documentação passa a mentir."""
    _login_admin(app, client)
    corpo = client.get(
        "/static/modelo_paginas_nice_admin/_modelo-pagina-completo.html"
    ).data.decode("utf-8")

    assert "/api/brewstation/yeast-strains" in corpo          # API REST do CrudGen
    assert "/admin/designer/data-action/" in corpo            # Ação de Dado
    assert "/api/options/" in corpo                           # opções de combo
    assert "nav-tabs-bordered" in corpo                       # controle de abas
    assert "SUA_ENTIDADE" in corpo                            # o que trocar


def test_modelo_completo_escapa_dado_da_api(app, client):
    """O HTML da página é confiável; o dado que volta da API não é. Sem
    escape, um registro com <script> no nome vira XSS."""
    _login_admin(app, client)
    corpo = client.get(
        "/static/modelo_paginas_nice_admin/_modelo-pagina-completo.html"
    ).data.decode("utf-8")

    assert "esc(" in corpo
    assert "&amp;lt;" in corpo or "&lt;" in corpo
    # nenhuma interpolação de dado da API sem passar por esc()
    assert "${r.name}" not in corpo
    assert "${esc(r.name)}" in corpo


def test_skill_17_existe_e_cobre_os_tres_caminhos():
    from pathlib import Path

    doc = Path("docs/skills/17-paginas-customizadas-fluxo-de-dados.md").read_text(encoding="utf-8")
    assert "/admin/designer/data-action/" in doc
    assert "/api/options/" in doc
    assert "401" in doc and "403" in doc
    assert "SSTI" in doc
    assert "CSRF" in doc


# ── o que foi preservado ──────────────────────────────────────────────

def test_execucao_de_acao_de_dado_continua_funcionando(app, client):
    from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain

    with app.app_context():
        db.session.add(YeastStrain(name="Preservada", status="disponivel"))
        conn = ODataConnection.query.filter_by(is_local=True).first()
        action = DesignerDataAction(
            name="Listar", connection_id=conn.id, entity_name="yeast_strain", operation="query",
        )
        db.session.add(action)
        db.session.commit()
        action_id = action.id

    _login_admin(app, client)
    resp = client.post(f"/admin/designer/data-action/{action_id}/execute", json={})
    assert resp.status_code == 200
    assert any(r["name"] == "Preservada" for r in resp.get_json()["result"]["value"])


def test_substituicao_de_menu_continua_funcionando(app, client):
    from model.core.transaction import Transaction

    _login_admin(app, client)
    page_id = _page(client)
    client.post(f"/admin/designer/{page_id}/settings", data={
        "replaces_entity_key": "yeast_strains",
        "replaces_view": "manage",
        "replace_in_menu": "on",
    })
    client.post(f"/admin/designer/{page_id}/publish")

    with app.app_context():
        slug = DesignerPage.query.get(page_id).slug
        tx = Transaction.query.filter_by(permission_required="yeast_strains.list").first()
        assert tx.route == f"/designer/{slug}"


# ── guarda de boot com migration pendente ─────────────────────────────

def test_resolver_de_menu_tolera_schema_desatualizado(app):
    """ACHADO REAL (repetido): `run.py` usa FlaskGroup, então
    `create_app()` — com todos os seeds e resolvers de boot — roda ANTES
    de qualquer subcomando `flask db ...`, inclusive `db upgrade`. Numa
    instalação existente com a migration da Fase 12 pendente, a coluna
    `content_html` ainda não existe, e sem esta guarda o boot inteiro
    quebrava — impedindo justamente o `flask db upgrade` que criaria a
    coluna (galinha e ovo). Mesma guarda já aplicada em
    core/odata_local_seed.py.
    """
    from sqlalchemy.exc import OperationalError
    from core import designer_menu_override

    class _PaginaComSchemaAntigo:
        class query:
            @staticmethod
            def filter_by(**kwargs):
                raise OperationalError(
                    "SELECT content_html FROM tesseract_designer_page", {},
                    Exception("no such column: tesseract_designer_page.content_html"),
                )

    original = designer_menu_override.DesignerPage
    designer_menu_override.DesignerPage = _PaginaComSchemaAntigo
    try:
        with app.app_context():
            # não pode levantar: se levantar, o boot morre e o usuário
            # nunca consegue rodar a migration que corrige o schema.
            designer_menu_override.resolve_designer_page_menu_overrides()
    finally:
        designer_menu_override.DesignerPage = original
