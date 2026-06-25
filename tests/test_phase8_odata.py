"""
tests/test_phase8_odata.py

Cobre a Fase 8 (escopo recortado, decisão registrada em BACKLOG.md):
ODataConnectionManager (descoberta de metadata, query) + telas de
gestão de conexão e navegador de dados read-only. Geração de tela
completa (screen_generator.py do DEVStationFlask) fica fora —
depende do Designer (Fase 7c), que ainda não existe.

Usa um servidor HTTP local de mentira (stdlib http.server) simulando
um servidor OData v4 real — sem isso, não dá pra validar a descoberta
de metadata de ponta a ponta.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.odata_connection import ODataConnection


FAKE_METADATA = {
    "entities": [{
        "name": "Customers", "label": "Customers",
        "fields": [
            {"name": "Id", "type": "NUMBER"},
            {"name": "Name", "type": "TEXT"},
            {"name": "City", "type": "TEXT"},
        ],
        "ui": {},
    }]
}
FAKE_DATA = {
    "value": [
        {"Id": 1, "Name": "Acme Corp", "City": "Sao Paulo"},
        {"Id": 2, "Name": "Beta Ltda", "City": "Curitiba"},
    ],
    "@odata.count": 2,
}


class _MockODataHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if "$metadata.json" in self.path or "%24metadata.json" in self.path:
            body = json.dumps(FAKE_METADATA).encode()
        elif "/Customers" in self.path:
            body = json.dumps(FAKE_DATA).encode()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def mock_odata_server():
    server = HTTPServer(("127.0.0.1", 0), _MockODataHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/odata/"
    server.shutdown()


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


# ── ODataConnectionManager (unitário, sem HTTP do Flask) ────────────────────

def test_connection_manager_descobre_metadata_json(app, mock_odata_server):
    from core.odata.connection_manager import ODataConnectionManager

    with app.app_context():
        conn = ODataConnection(name="Teste", base_url=mock_odata_server)
        db.session.add(conn)
        db.session.commit()

        result = ODataConnectionManager(conn).test_connection()
        assert result["ok"] is True
        assert result["entities_count"] == 1
        assert result["source_format"] == "json"


def test_connection_manager_lista_entidades(app, mock_odata_server):
    from core.odata.connection_manager import ODataConnectionManager

    with app.app_context():
        conn = ODataConnection(name="Teste", base_url=mock_odata_server)
        db.session.add(conn)
        db.session.commit()

        entities = ODataConnectionManager(conn).list_entities()
        assert len(entities) == 1
        assert entities[0]["name"] == "Customers"
        assert len(entities[0]["fields"]) == 3


def test_connection_manager_query_retorna_dados_reais(app, mock_odata_server):
    from core.odata.connection_manager import ODataConnectionManager

    with app.app_context():
        conn = ODataConnection(name="Teste", base_url=mock_odata_server)
        db.session.add(conn)
        db.session.commit()

        result = ODataConnectionManager(conn).query("Customers")
        names = [r["Name"] for r in result["value"]]
        assert set(names) == {"Acme Corp", "Beta Ltda"}


def test_connection_manager_cacheia_metadata(app, mock_odata_server):
    from core.odata.connection_manager import ODataConnectionManager

    with app.app_context():
        conn = ODataConnection(name="Teste", base_url=mock_odata_server)
        db.session.add(conn)
        db.session.commit()

        mgr = ODataConnectionManager(conn)
        mgr.fetch_metadata()
        assert conn.metadata_cache is not None
        assert conn.metadata_cached_at is not None


def test_connection_manager_falha_com_url_invalida(app):
    from core.odata.connection_manager import ODataConnectionManager

    with app.app_context():
        conn = ODataConnection(name="Inválida", base_url="http://127.0.0.1:1/nao-existe/")
        db.session.add(conn)
        db.session.commit()

        result = ODataConnectionManager(conn).test_connection()
        assert result["ok"] is False
        assert "error" in result


# ── Telas (clique real via HTTP) ────────────────────────────────────────────

def test_tela_de_conexoes_abre(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/odata/")
    assert resp.status_code == 200


def test_criar_conexao_pela_tela(app, client, mock_odata_server):
    _login_admin(app, client)
    resp = client.post(
        "/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server},
        follow_redirects=True,
    )
    assert "criada".encode() in resp.data

    with app.app_context():
        assert ODataConnection.query.filter_by(name="Mock Test").first() is not None


def test_testar_conexao_pela_tela(app, client, mock_odata_server):
    _login_admin(app, client)
    client.post("/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server})
    with app.app_context():
        conn_id = ODataConnection.query.first().id

    resp = client.post(f"/admin/odata/{conn_id}/test", follow_redirects=True)
    assert "entidade".encode() in resp.data


def test_ver_entidades_pela_tela(app, client, mock_odata_server):
    _login_admin(app, client)
    client.post("/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server})
    with app.app_context():
        conn_id = ODataConnection.query.first().id

    resp = client.get(f"/admin/odata/{conn_id}/entities")
    assert resp.status_code == 200
    assert b"Customers" in resp.data


def test_navegar_dados_mostra_registros_reais(app, client, mock_odata_server):
    _login_admin(app, client)
    client.post("/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server})
    with app.app_context():
        conn_id = ODataConnection.query.first().id
    client.post(f"/admin/odata/{conn_id}/test")

    resp = client.get(f"/admin/odata/{conn_id}/browse/Customers")
    assert resp.status_code == 200
    assert b"Acme Corp" in resp.data
    assert b"Beta Ltda" in resp.data


def test_navegar_entidade_inexistente_redireciona_com_erro(app, client, mock_odata_server):
    _login_admin(app, client)
    client.post("/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server})
    with app.app_context():
        conn_id = ODataConnection.query.first().id
    client.post(f"/admin/odata/{conn_id}/test")

    resp = client.get(f"/admin/odata/{conn_id}/browse/EntidadeFake", follow_redirects=True)
    assert "não encontrada".encode() in resp.data


def test_remover_conexao(app, client, mock_odata_server):
    _login_admin(app, client)
    client.post("/admin/odata/", data={"name": "Mock Test", "base_url": mock_odata_server})
    with app.app_context():
        conn_id = ODataConnection.query.first().id

    client.post(f"/admin/odata/{conn_id}/delete")

    with app.app_context():
        assert ODataConnection.query.get(conn_id) is None
