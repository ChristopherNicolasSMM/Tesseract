"""
tests/test_ingredientes_workspace.py

Cobre: tela consolidada de Insumos (is_workspace=True), API de preço
padrão por tipo (GET/PUT) e o destaque na home (faixa "Fluxos" só
com is_workspace=True, sem duplicar nem esconder as telas normais).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.transaction import Transaction
from addons.addon_brewstation.features.feature_ingredientes.model.preco_padrao_insumo import PrecoPadraoInsumo


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


def test_workspace_exige_login(client):
    resp = client.get("/brewstation/ingredientes-workspace/")
    assert resp.status_code in (302, 401)


def test_workspace_renderiza_logado_com_3_abas(app, client):
    _login_admin(app, client)
    resp = client.get("/brewstation/ingredientes-workspace/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Malte" in html
    assert "Lúpulo" in html
    assert "Levedura" in html


def test_seed_cria_as_3_linhas_de_preco_padrao(app):
    with app.app_context():
        tipos = {p.tipo_insumo for p in PrecoPadraoInsumo.query.all()}
        assert tipos == {"malte", "lupulo", "levedura"}


def test_api_lista_precos_padrao(app, client):
    _login_admin(app, client)
    resp = client.get("/api/brewstation/preco-padrao-insumos/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["items"]) == 3


def test_api_edita_preco_padrao_via_popup(app, client):
    _login_admin(app, client)
    resp = client.put("/api/brewstation/preco-padrao-insumos/malte", json={"valor_padrao": 30.5})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["item"]["valor_padrao"] == 30.5

    with app.app_context():
        row = PrecoPadraoInsumo.query.filter_by(tipo_insumo="malte").first()
        assert row.valor_padrao == 30.5


def test_api_rejeita_valor_negativo(app, client):
    _login_admin(app, client)
    resp = client.put("/api/brewstation/preco-padrao-insumos/malte", json={"valor_padrao": -5})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_api_rejeita_tipo_insumo_invalido(app, client):
    _login_admin(app, client)
    resp = client.put("/api/brewstation/preco-padrao-insumos/inexistente", json={"valor_padrao": 10})
    assert resp.status_code == 400


def test_home_mostra_faixa_fluxos_com_workspace_de_ingredientes(app, client):
    _login_admin(app, client)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Fluxos" in html
    assert "Insumos (Malte / Lúpulo / Levedura)" in html
    # Telas individuais continuam presentes — nada foi desativado.
    assert "/brewstation/maltes" in html
    assert "/brewstation/lupulos" in html
    assert "/brewstation/leveduras" in html


def test_transacao_workspace_nao_afeta_as_outras_do_grupo(app):
    with app.app_context():
        maltes = Transaction.query.filter_by(code="TX_MALTES").first()
        workspace = Transaction.query.filter_by(code="TX_INGREDIENTES_WORKSPACE").first()
        assert maltes is not None and maltes.is_active is True and maltes.is_workspace is False
        assert workspace is not None and workspace.is_workspace is True
