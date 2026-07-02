"""
tests/test_playground.py

Cobre o API/SQL Playground (skill 06, Patch C): validação SELECT-only
(skill 06 §6), execução real de SQL/HTTP (HTTP mockado — sandbox de
teste não tem acesso à rede externa), inferência de campos a partir de
JSON (skill 06 §5), e a ponte com o Model Builder.
"""
from unittest.mock import patch, Mock

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.permission import Permission
from services.core import playground_service as svc


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Validação SELECT-only (skill 06 §6) ─────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "INSERT INTO tesseract_user (username) VALUES ('x')",
    "UPDATE tesseract_user SET username='x'",
    "DELETE FROM tesseract_user",
    "DROP TABLE tesseract_user",
    "ALTER TABLE tesseract_user ADD COLUMN x TEXT",
    "SELECT * FROM tesseract_user; DROP TABLE tesseract_user",
    "TRUNCATE TABLE tesseract_user",
])
def test_sql_nao_select_e_sempre_rejeitado(app, sql):
    with app.app_context():
        with pytest.raises(svc.PlaygroundError):
            svc.execute_sql_select(name=None, sql_text=sql)


def test_sql_select_simples_executa_e_retorna_linhas(app):
    with app.app_context():
        record = svc.execute_sql_select(name="teste", sql_text="SELECT 1 AS um")
        assert record.last_error is None
        assert record.last_response_json["columns"] == ["um"]
        assert record.last_response_json["rows"] == [[1]]


def test_sql_com_cte_with_e_aceito(app):
    with app.app_context():
        record = svc.execute_sql_select(
            name="teste-cte",
            sql_text="WITH x AS (SELECT 1 AS um) SELECT * FROM x",
        )
        assert record.last_error is None
        assert record.last_response_json["rows"] == [[1]]


def test_sql_com_erro_de_sintaxe_fica_no_historico_com_erro(app):
    with app.app_context():
        with pytest.raises(svc.PlaygroundError):
            svc.execute_sql_select(name=None, sql_text="SELECT FROM ONDE_NAO_EXISTE")

        from model.core.playground_request import PlaygroundRequest
        record = PlaygroundRequest.query.filter_by(sql_text="SELECT FROM ONDE_NAO_EXISTE").first()
        assert record is not None
        assert record.last_error is not None


# ── HTTP (mockado — sandbox de teste sem rede externa) ──────────────────────

def test_http_get_bem_sucedido(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {"nome": "Cerveja Teste", "abv": 5.2}

    with app.app_context():
        with patch("services.core.playground_service.requests.request", return_value=fake_response) as mocked:
            record = svc.execute_http_request(
                name="teste", method="get", url="https://api.exemplo.local/receita",
            )
            mocked.assert_called_once()
            assert record.last_status_code == 200
            assert record.last_response_json == {"nome": "Cerveja Teste", "abv": 5.2}
            assert record.last_error is None


def test_http_falha_de_rede_fica_registrada_sem_derrubar(app):
    import requests as requests_module

    with app.app_context():
        with patch(
            "services.core.playground_service.requests.request",
            side_effect=requests_module.ConnectionError("falha simulada"),
        ):
            record = svc.execute_http_request(name=None, method="GET", url="https://indisponivel.local/x")
            assert record.last_error is not None
            assert record.last_status_code is None


# ── Inferência de campos (skill 06 §5) ──────────────────────────────────────

def test_inferir_campos_de_objeto_unico():
    fields = svc.infer_fields_from_json({"nome": "Teste", "quantidade": 10, "ativo": True})
    by_name = {f["field_name"]: f for f in fields}
    assert by_name["nome"]["field_type"] == "string"
    assert by_name["quantidade"]["field_type"] == "integer"
    assert by_name["ativo"]["field_type"] == "boolean"


def test_inferir_campos_de_lista_marca_nullable_quando_chave_falta_em_algum_item():
    fields = svc.infer_fields_from_json([
        {"nome": "A", "opcional": "x"},
        {"nome": "B"},
    ])
    by_name = {f["field_name"]: f for f in fields}
    assert by_name["nome"]["nullable"] is False
    assert by_name["opcional"]["nullable"] is True


def test_inferir_campos_de_lista_vazia_retorna_vazio():
    assert svc.infer_fields_from_json([]) == []


# ── Ponte com o Model Builder ────────────────────────────────────────────

def test_bridge_cria_rascunho_com_campos_inferidos(app):
    with app.app_context():
        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {"titulo": "X", "quantidade": 3}
        with patch("services.core.playground_service.requests.request", return_value=fake_response):
            record = svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")

        definition = svc.create_model_definition_from_playground(
            record.id,
            target_addon_name="brewstation", target_feature_name=None,
            model_name="BridgeWidget", table_short_name="bridge_widget",
            created_by_user_id=None,
        )
        field_names = {f.field_name for f in definition.fields}
        assert field_names == {"titulo", "quantidade"}


def test_bridge_sem_resposta_salva_falha(app):
    with app.app_context():
        from model.core.playground_request import PlaygroundRequest, PlaygroundRequestKind
        record = PlaygroundRequest(kind=PlaygroundRequestKind.HTTP, http_method="GET", url="x")
        db.session.add(record)
        db.session.commit()

        with pytest.raises(svc.PlaygroundError):
            svc.create_model_definition_from_playground(
                record.id, target_addon_name="brewstation", target_feature_name=None,
                model_name="SemResposta", table_short_name="sem_resposta", created_by_user_id=None,
            )


# ── Rotas web ────────────────────────────────────────────────────────────

def test_tela_manage_carrega(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/playground/")
    assert resp.status_code == 200
    assert b"Playground" in resp.data


def test_rota_sql_via_http(app, client):
    _login_admin(app, client)
    resp = client.post("/admin/playground/sql", data={"sql_text": "SELECT 1"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"OK" in resp.data or b"1 linha" in resp.data


def test_rota_sql_rejeita_insert_via_http(app, client):
    _login_admin(app, client)
    resp = client.post(
        "/admin/playground/sql",
        data={"sql_text": "INSERT INTO tesseract_user (username) VALUES ('x')"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"SELECT" in resp.data  # mensagem de erro menciona a regra


def test_permissao_playground_seedada_no_boot(app):
    with app.app_context():
        assert Permission.query.filter_by(name="playground_requests.execute").first() is not None
