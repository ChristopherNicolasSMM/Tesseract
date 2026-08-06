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
