"""
tests/test_playground_v2.py

Cobre a adenda "Playground v2" da skill 06 (§8): Auth dedicada,
Query Params estruturados, cookie jar por usuário, pastas em árvore
N-níveis, e arquivar/apagar como ações separadas.
"""
from unittest.mock import patch, Mock

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.playground_request import PlaygroundRequest, PlaygroundAuthType
from model.core.playground_folder import PlaygroundFolder
from model.core.playground_cookie_jar import PlaygroundCookieJar
from services.core import playground_service as svc


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_admin(app):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
        return User.query.filter_by(username="admin").first().id


def _login_admin(app, client):
    _create_admin(app)
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Auth dedicada (skill 06 §8.1) ───────────────────────────────────────────

def test_auth_bearer_gera_header_authorization(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(
                name=None, method="GET", url="https://api.exemplo.local/x",
                auth_type=PlaygroundAuthType.BEARER, auth_config={"token": "abc123"},
            )
            _, kwargs = mocked.call_args
            assert kwargs["headers"]["Authorization"] == "Bearer abc123"


def test_auth_basic_gera_header_authorization_base64(app):
    import base64
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(
                name=None, method="GET", url="https://api.exemplo.local/x",
                auth_type=PlaygroundAuthType.BASIC,
                auth_config={"username": "joao", "password": "123"},
            )
            _, kwargs = mocked.call_args
            expected = "Basic " + base64.b64encode(b"joao:123").decode()
            assert kwargs["headers"]["Authorization"] == expected


def test_auth_api_key_usa_header_customizado(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(
                name=None, method="GET", url="https://api.exemplo.local/x",
                auth_type=PlaygroundAuthType.API_KEY,
                auth_config={"header_name": "X-Api-Key", "value": "segredo"},
            )
            _, kwargs = mocked.call_args
            assert kwargs["headers"]["X-Api-Key"] == "segredo"


def test_headers_livres_convivem_com_auth(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(
                name=None, method="GET", url="https://api.exemplo.local/x",
                headers={"Accept": "application/json"},
                auth_type=PlaygroundAuthType.BEARER, auth_config={"token": "tok"},
            )
            _, kwargs = mocked.call_args
            assert kwargs["headers"]["Accept"] == "application/json"
            assert kwargs["headers"]["Authorization"] == "Bearer tok"


# ── Query Params estruturados (skill 06 §8.0/§8.1) ──────────────────────────

def test_params_habilitados_viram_query_string(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(
                name=None, method="GET", url="https://api.exemplo.local/x",
                params=[
                    {"key": "page", "value": "2", "enabled": True},
                    {"key": "ignored", "value": "x", "enabled": False},
                ],
            )
            _, kwargs = mocked.call_args
            assert kwargs["params"] == {"page": "2"}


def test_sem_params_nao_envia_query_string(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")
            _, kwargs = mocked.call_args
            assert kwargs["params"] is None


# ── Cookie jar por usuário (skill 06 §8.1) ──────────────────────────────────

def test_cookie_jar_persiste_e_e_reaproveitado_na_proxima_chamada(app):
    user_id = _create_admin(app)

    with app.app_context():
        # 1ª chamada: servidor "manda" um cookie de sessão
        fake_response_1 = Mock(status_code=200)
        fake_response_1.json.return_value = {}

        def _fake_request_1(self, *args, **kwargs):
            self.cookies.set("session_id", "abc123")
            return fake_response_1

        with patch("services.core.playground_service.requests.Session.request", _fake_request_1):
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/login",
                                      created_by_user_id=user_id)

        jar = PlaygroundCookieJar.query.filter_by(user_id=user_id).first()
        assert jar is not None
        assert jar.cookies_json.get("session_id") == "abc123"

        # 2ª chamada: a sessão pré-carrega o cookie salvo — captura o
        # que efetivamente foi enviado pra confirmar o reaproveitamento.
        fake_response_2 = Mock(status_code=200)
        fake_response_2.json.return_value = {}
        captured = {}

        def _capture_cookies(self, *args, **kwargs):
            captured["cookies_no_envio"] = dict(self.cookies)
            return fake_response_2

        with patch("services.core.playground_service.requests.Session.request", _capture_cookies):
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/dados",
                                      created_by_user_id=user_id)

        assert captured["cookies_no_envio"].get("session_id") == "abc123"


def test_sem_usuario_nao_grava_cookie_jar(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x",
                                      created_by_user_id=None)
        assert PlaygroundCookieJar.query.count() == 0


# ── Pastas em árvore N-níveis (skill 06 §8.2) ───────────────────────────────

def test_criar_pasta_e_subpasta(app):
    with app.app_context():
        raiz = svc.create_folder(name="BrewFather")
        sub = svc.create_folder(name="Receitas", parent_id=raiz.id)
        tree = svc.list_folder_tree()
        by_name = {f["name"]: f for f in tree}
        assert by_name["BrewFather"]["depth"] == 0
        assert by_name["Receitas"]["depth"] == 1
        assert by_name["Receitas"]["parent_id"] == raiz.id


def test_apagar_pasta_vazia_funciona(app):
    with app.app_context():
        folder = svc.create_folder(name="Temp")
        svc.delete_folder(folder.id)
        assert PlaygroundFolder.query.get(folder.id) is None


def test_apagar_pasta_com_subpasta_e_bloqueado(app):
    with app.app_context():
        raiz = svc.create_folder(name="Pai")
        svc.create_folder(name="Filha", parent_id=raiz.id)
        with pytest.raises(svc.PlaygroundError):
            svc.delete_folder(raiz.id)


def test_apagar_pasta_com_requisicao_e_bloqueado(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        folder = svc.create_folder(name="ComRequest")
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x", folder_id=folder.id)
        with pytest.raises(svc.PlaygroundError):
            svc.delete_folder(folder.id)


def test_mover_requisicao_de_pasta(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        folder = svc.create_folder(name="Destino")
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            record = svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")
        assert record.folder_id is None
        svc.move_request_to_folder(record.id, folder.id)
        assert PlaygroundRequest.query.get(record.id).folder_id == folder.id


# ── Arquivar vs. Apagar (skill 06 §8.3) ─────────────────────────────────────

def test_arquivar_e_desarquivar(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            record = svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")
        assert record.is_archived is False

        svc.set_archived(record.id, True)
        assert PlaygroundRequest.query.get(record.id).is_archived is True

        svc.set_archived(record.id, False)
        assert PlaygroundRequest.query.get(record.id).is_archived is False


def test_apagar_e_definitivo(app):
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            record = svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")
        record_id = record.id
        svc.delete_request(record_id)
        assert PlaygroundRequest.query.get(record_id) is None


# ── Rotas web ────────────────────────────────────────────────────────────

def test_tela_manage_lista_pastas(app, client):
    _login_admin(app, client)
    with app.app_context():
        svc.create_folder(name="Minha Pasta")
    resp = client.get("/admin/playground/")
    assert resp.status_code == 200
    assert b"Minha Pasta" in resp.data


def test_criar_pasta_pela_tela(app, client):
    _login_admin(app, client)
    resp = client.post("/admin/playground/folders", data={"name": "Via Tela"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert PlaygroundFolder.query.filter_by(name="Via Tela").first() is not None


def test_arquivar_e_apagar_pela_tela(app, client):
    _login_admin(app, client)
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {}
    with app.app_context():
        with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
            record = svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")
        record_id = record.id

    resp = client.post(f"/admin/playground/{record_id}/archive", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert PlaygroundRequest.query.get(record_id).is_archived is True

    resp = client.post(f"/admin/playground/{record_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert PlaygroundRequest.query.get(record_id) is None


def test_execute_http_com_auth_e_params_pela_tela(app, client):
    _login_admin(app, client)
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {"ok": True}
    with patch("services.core.playground_service.requests.Session.request", return_value=fake_response) as mocked:
        resp = client.post(
            "/admin/playground/http",
            data={
                "http_method": "GET",
                "url": "https://api.exemplo.local/x",
                "auth_type": "bearer",
                "auth_bearer_token": "tok123",
                "params_json": '[{"key": "page", "value": "1", "enabled": true}]',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        _, kwargs = mocked.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer tok123"
        assert kwargs["params"] == {"page": "1"}


# ── Bridge "use-as-fields" também usa select de addon/feature (BACKLOG.md) ──

def test_tela_manage_playground_lista_addons_no_select_da_ponte(app, client):
    _login_admin(app, client)
    fake_response = Mock(status_code=200)
    fake_response.json.return_value = {"ok": True}
    with patch("services.core.playground_service.requests.Session.request", return_value=fake_response):
        with app.app_context():
            svc.execute_http_request(name=None, method="GET", url="https://api.exemplo.local/x")

    resp = client.get("/admin/playground/")
    assert resp.status_code == 200
    assert b"pg-bridge-addon" in resp.data
    assert b"pg-bridge-feature" in resp.data
