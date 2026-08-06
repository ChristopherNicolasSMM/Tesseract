"""
tests/test_freestyle_modelos.py

Modelos de referência freestyle (/freestyle/*) — telas escritas à mão,
fora do CrudGen, renderizadas dentro do layout real.
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


def _login(app, client, is_admin=True):
    with app.app_context():
        user = User(
            username="admin", email="admin@test.local",
            nome="Admin", nome_completo="Administrador", celular="11999999999",
            is_admin=is_admin, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})


ROTAS = ["/freestyle/", "/freestyle/minimal", "/freestyle/abas",
         "/freestyle/consumption", "/freestyle/full"]


@pytest.mark.parametrize("rota", ROTAS)
def test_rota_exige_login(client, rota):
    resp = client.get(rota)
    assert resp.status_code in (302, 401)


@pytest.mark.parametrize("rota", ROTAS)
def test_rota_renderiza_logado(app, client, rota):
    _login(app, client)
    resp = client.get(rota)
    assert resp.status_code == 200


def test_indice_linka_os_quatro_modelos(app, client):
    _login(app, client)
    body = client.get("/freestyle/").data.decode()
    for rota in ["/freestyle/minimal", "/freestyle/abas",
                 "/freestyle/consumption", "/freestyle/full"]:
        assert rota in body


def test_minimal_nao_tem_resto_do_designer_page(app, client):
    """O template nasceu copiado do runtime do DesignerPage, onde `page`
    era o objeto da página. Aqui não existe esse objeto — `page.title` e
    `page.content_html` renderizariam vazio em silêncio."""
    _login(app, client)
    body = client.get("/freestyle/minimal").data.decode()
    assert "content_html" not in body
    assert "<h1>Modelo Mínimo</h1>" in body


def test_abas_carrega_js_de_static_nao_de_templates(app, client):
    """JS sob templates/ não é servível — o Flask serve static/. Um
    <script src> apontando para templates/ retorna 404."""
    _login(app, client)
    body = client.get("/freestyle/abas").data.decode()
    assert "/static/js/freestyle/model_abas-tabs.js" in body
    assert "templates/core/freestyle/js" not in body


def test_js_de_abas_e_servido(app, client):
    _login(app, client)
    resp = client.get("/static/js/freestyle/model_abas-tabs.js")
    assert resp.status_code == 200
    assert b"replaceState" in resp.data


def test_abas_tem_as_variacoes_documentadas(app, client):
    _login(app, client)
    body = client.get("/freestyle/abas").data.decode()
    assert "nav-tabs-bordered" in body
    assert "flex-column" in body          # abas verticais
    assert "data-abas-persistir" in body  # persistência na URL
    assert "disabled" in body             # aba desabilitada


def test_consumption_recebe_config_do_controller(app, client):
    """O controller passa page/per_page/q e o bloco `config` — é o
    mecanismo de passar variáveis do servidor para a tela."""
    _login(app, client)
    resp = client.get("/freestyle/consumption?page=3&per_page=50&q=ale")
    assert resp.status_code == 200


def test_consumption_limita_per_page(app):
    """`page`/`per_page` vêm da URL, ou seja, do usuário. Sem clamp,
    ?per_page=999999 vira uma consulta que derruba a tela."""
    from controller.core import freestyle_model
    import inspect

    fonte = inspect.getsource(freestyle_model.consumption)
    assert "min(max(per_page" in fonte
    assert "max(1, page)" in fonte


def test_transacao_no_menu_em_ferramentas(app):
    with app.app_context():
        tx = Transaction.query.filter_by(code="TX_ADMIN_FREESTYLE").first()
        assert tx is not None
        assert tx.route == "/freestyle/"
        assert tx.parent.code == "TX_GROUP_FERRAMENTAS_DE_DESENVOLVIMENTO"


# ── Patch 2/3: modelo de consumo de dados ─────────────────────────────

def test_consumption_nao_e_mais_placeholder(app, client):
    _login(app, client)
    body = client.get("/freestyle/consumption").data.decode()
    assert "Em construção" not in body
    assert "Consumo de Dados" in body


def test_consumption_serializa_config_como_json(app, client):
    """O config vai num <script type="application/json">, não montado
    por concatenação no Jinja — assim aspa/acento do servidor não
    quebram o script nem viram vetor de XSS."""
    _login(app, client)
    body = client.get("/freestyle/consumption?q=ale&per_page=50").data.decode()
    assert 'type="application/json" id="freestyle-config"' in body
    assert '"restBase"' in body
    assert '"perPage": 50' in body or '"perPage":50' in body


def test_consumption_reflete_estado_da_url_no_html(app, client):
    """A URL é o estado da tela: o campo de busca e o seletor de
    tamanho de página nascem preenchidos, sem 'piscar' o padrão."""
    _login(app, client)
    body = client.get("/freestyle/consumption?q=saison&per_page=100").data.decode()
    assert 'value="saison"' in body
    assert '<option value="100" selected>' in body


def test_consumption_carrega_os_dois_js_na_ordem(app, client):
    """O helper define window.TesseractData; o segundo arquivo consome.
    Ordem trocada = ReferenceError."""
    _login(app, client)
    body = client.get("/freestyle/consumption").data.decode()
    pos_helper = body.index("freestyle-tesseract-data.js")
    pos_telas = body.index("model_consumption-telas.js")
    assert pos_helper < pos_telas


@pytest.mark.parametrize("arquivo", [
    "freestyle-tesseract-data.js",
    "model_consumption-telas.js",
])
def test_js_de_consumo_sao_servidos(app, client, arquivo):
    _login(app, client)
    resp = client.get(f"/static/js/freestyle/{arquivo}")
    assert resp.status_code == 200


def test_helper_cobre_os_tres_caminhos(app, client):
    _login(app, client)
    js = client.get("/static/js/freestyle/freestyle-tesseract-data.js").data.decode()
    assert "/admin/designer/data-action/" in js   # Ação de Dado
    assert "/api/options/" in js                  # opções de combo
    assert "rest:" in js                          # API REST do CrudGen
    assert "401" in js and "403" in js            # sessão vs permissão


def test_js_de_consumo_escapa_dado_da_api(app, client):
    """Sem esc(), um registro com <script> no nome vira XSS."""
    _login(app, client)
    js = client.get("/static/js/freestyle/model_consumption-telas.js").data.decode()
    assert "esc(r.name)" in js
    assert "+ r.name +" not in js


def test_sem_acao_de_dado_explica_em_vez_de_falhar(app, client):
    """dataActionId vem None do controller — a seção precisa orientar,
    não disparar um 404 silencioso."""
    _login(app, client)
    body = client.get("/freestyle/consumption").data.decode()
    assert "Nenhuma Ação de Dado configurada" in body
