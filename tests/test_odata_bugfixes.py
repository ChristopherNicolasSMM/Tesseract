"""
tests/test_odata_bugfixes.py

Cobre os 2 bugs de OData registrados em BACKLOG.md ("Bugs de OData"):

1. Descoberta de $metadata quebrada quando a `base_url` cadastrada já
   é a própria URL de metadata (em vez da raiz do serviço).
2. Browse usando EntityType.Name (singular) em vez de EntitySet.Name
   (plural, real) para montar a URL de coleção — cobre tanto o caso
   EDMX real (XML) quanto o fallback de pluralização + override manual
   para o formato customizado sem EntitySet.

Servidor HTTP local de mentira (stdlib http.server), igual ao padrão
já usado em tests/test_phase8_odata.py.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.odata_connection import ODataConnection


def _make_handler(routes: dict):
    """`routes`: {path_substring: (status_code, content_type, body_bytes)}.
    Primeiro match por `in` vence."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            for key, (status, ctype, body) in routes.items():
                if key in self.path:
                    self.send_response(status)
                    self.send_header("Content-Type", ctype)
                    self.end_headers()
                    self.wfile.write(body)
                    return
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode())

    return _Handler


def _start_server(routes: dict):
    server = HTTPServer(("127.0.0.1", 0), _make_handler(routes))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


# ── Bug 1: base_url já aponta pro próprio $metadata ─────────────────────────

EDMX_XML_SIMPLES = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0" xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="Demo" xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <EntityType Name="Product">
        <Key><PropertyRef Name="ProductID"/></Key>
        <Property Name="ProductID" Type="Edm.Int32" Nullable="false"/>
        <Property Name="ProductName" Type="Edm.String" MaxLength="40"/>
      </EntityType>
      <EntityContainer Name="DemoContainer">
        <EntitySet Name="Products" EntityType="Demo.Product"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


def test_bug1_base_url_ja_e_o_proprio_metadata(app):
    """Reproduz o caso real relatado: a conexão foi cadastrada com a
    URL do $metadata em vez da raiz do serviço — antes do bugfix,
    isso gerava 404 em cascata (.../$metadata/$metadata.json etc)."""
    from core.odata.connection_manager import ODataConnectionManager

    server = _start_server({
        "$metadata": (200, "application/xml", EDMX_XML_SIMPLES),
    })
    port = server.server_port
    try:
        with app.app_context():
            conn = ODataConnection(
                name="Teste", base_url=f"http://127.0.0.1:{port}/odata/$metadata",
            )
            db.session.add(conn)
            db.session.commit()

            result = ODataConnectionManager(conn).test_connection()
            assert result["ok"] is True
            assert result["entities_count"] == 1
    finally:
        server.shutdown()


# ── Bug 2a: EDMX real — EntitySet.Name (plural) usado como rota ────────────

def test_bug2_edmx_usa_entityset_name_como_rota(app):
    from core.odata.connection_manager import ODataConnectionManager

    products_data = json.dumps({
        "value": [{"ProductID": 1, "ProductName": "Chai"}],
    }).encode()

    server = _start_server({
        "%24metadata.json": (404, "application/json", b"{}"),
        "$metadata": (200, "application/xml", EDMX_XML_SIMPLES),
        "/odata/Products": (200, "application/json", products_data),
    })
    port = server.server_port
    try:
        with app.app_context():
            conn = ODataConnection(name="Teste", base_url=f"http://127.0.0.1:{port}/odata/")
            db.session.add(conn)
            db.session.commit()

            mgr = ODataConnectionManager(conn)
            entities = mgr.list_entities()
            assert len(entities) == 1
            # Nome de rota é o EntitySet (plural), não o EntityType (singular)
            assert entities[0]["name"] == "Products"
            assert entities[0]["label"] == "Product"
            assert entities[0]["declared_name"] == "Products"

            result = mgr.query("Products")
            assert result["value"][0]["ProductName"] == "Chai"
    finally:
        server.shutdown()


# ── Bug 2b: formato sem EntitySet — fallback de pluralização + persistência ─

FAKE_S2M_METADATA = {
    "entities": [{
        "name": "Order", "label": "Pedidos",
        "fields": [{"name": "OrderID", "type": "NUMBER"}],
        "ui": {},
    }]
}


def test_bug2_fallback_pluraliza_e_persiste_override(app):
    from core.odata.connection_manager import ODataConnectionManager

    server = _start_server({
        "%24metadata.json": (200, "application/json", json.dumps(FAKE_S2M_METADATA).encode()),
        "/odata/Orders": (200, "application/json", json.dumps({"value": []}).encode()),
        # "/odata/Order" (singular) não existe -> 404 pelo default do handler
    })
    port = server.server_port
    try:
        with app.app_context():
            conn = ODataConnection(name="Teste", base_url=f"http://127.0.0.1:{port}/odata/")
            db.session.add(conn)
            db.session.commit()

            mgr = ODataConnectionManager(conn)
            entities = mgr.list_entities()
            assert entities[0]["name"] == "Order"  # ainda sem override

            result = mgr.query("Order")  # declarado no metadata, mas a rota real é "Orders"
            assert result == {"value": []}

            db.session.refresh(conn)
            assert conn.entity_route_overrides == {"Order": "Orders"}

            # Próxima listagem já reflete o override, sem precisar adivinhar de novo
            entities_depois = mgr.list_entities()
            assert entities_depois[0]["name"] == "Orders"
            assert entities_depois[0]["declared_name"] == "Order"
    finally:
        server.shutdown()


def test_bug2_override_manual_pela_tela(app):
    from core.odata.connection_manager import ODataConnectionManager

    server = _start_server({
        "%24metadata.json": (200, "application/json", json.dumps(FAKE_S2M_METADATA).encode()),
        "/odata/Pedidos": (200, "application/json", json.dumps({"value": []}).encode()),
    })
    port = server.server_port
    try:
        with app.app_context():
            conn = ODataConnection(name="Teste", base_url=f"http://127.0.0.1:{port}/odata/")
            db.session.add(conn)
            db.session.commit()

            mgr = ODataConnectionManager(conn)
            mgr.set_route_override("Order", "Pedidos")

            db.session.refresh(conn)
            assert conn.entity_route_overrides == {"Order": "Pedidos"}

            entities = mgr.list_entities()
            assert entities[0]["name"] == "Pedidos"

            result = mgr.query("Pedidos")
            assert result == {"value": []}
    finally:
        server.shutdown()


def test_bug2_override_manual_pela_rota_web(app):
    server = _start_server({
        "%24metadata.json": (200, "application/json", json.dumps(FAKE_S2M_METADATA).encode()),
    })
    port = server.server_port
    try:
        client = app.test_client()
        with app.app_context():
            admin = User(
                username="admin", email="admin@test.local",
                nome="Admin", nome_completo="Administrador", celular="11999999999",
                is_admin=True, is_active=True,
            )
            admin.set_password("senha123")
            db.session.add(admin)

            conn = ODataConnection(name="Teste", base_url=f"http://127.0.0.1:{port}/odata/")
            db.session.add(conn)
            db.session.commit()
            conn_id = conn.id

        client.post("/api/auth/login", json={"username": "admin", "password": "senha123"})

        resp = client.post(
            f"/admin/odata/{conn_id}/entities/override",
            data={"declared_name": "Order", "route_name": "Pedidos"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "atualizada".encode() in resp.data

        with app.app_context():
            conn = ODataConnection.query.get(conn_id)
            assert conn.entity_route_overrides == {"Order": "Pedidos"}
    finally:
        server.shutdown()
