"""
tests/test_fase10_patch2_provedor_local.py

Fase 10, Patch 2 — provedor OData do próprio Tesseract: registry de
@odata_expose, metadata enriquecido, query/patch em processo, rotas
HTTP (/api/odata-provider/...), e o atalho em processo dentro de
ODataConnectionManager quando ODataConnection.is_local. Usa
YeastStrain como entidade real de prova (já marcada com
@odata_expose no model, Patch 2).
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User
from model.core.role import Role
from model.core.permission import Permission
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain

from core.odata_provider.registry import list_exposed_entities, get_exposed_entity
from core.odata_provider.metadata import build_metadata_json
from core.odata_provider.service import (
    query_local, patch_local, EntityNotExposedError, PermissionDeniedError,
)


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(app, username="admin", is_admin=True, permission_names=None):
    with app.app_context():
        user = User(
            username=username, email=f"{username}@test.local",
            nome=username, nome_completo=username.title(), celular="11999999999",
            is_admin=is_admin, is_active=True,
        )
        user.set_password("senha123")
        if permission_names:
            role = Role(name=f"role_{username}")
            for pname in permission_names:
                perm = Permission.query.filter_by(name=pname).first()
                if perm is None:
                    perm = Permission(name=pname)
                    db.session.add(perm)
                role.permissions.append(perm)
            db.session.add(role)
            user.roles.append(role)
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username="admin"):
    client.post("/api/auth/login", json={"username": username, "password": "senha123"})


def _seed_strain(app, name="Cepa Teste", status="disponivel"):
    with app.app_context():
        strain = YeastStrain(name=name, status=status)
        db.session.add(strain)
        db.session.commit()
        return strain.id


# ── registry ───────────────────────────────────────────────────────────

def test_registry_lista_yeast_strain(app):
    with app.app_context():
        entities = list_exposed_entities()
        assert "yeast_strain" in entities
        assert entities["yeast_strain"]["model"] is YeastStrain
        assert entities["yeast_strain"]["permission_required"] == "yeast_strains.list"


def test_registry_entidade_nao_exposta_retorna_none(app):
    with app.app_context():
        assert get_exposed_entity("entidade_que_nao_existe") is None


# ── metadata ───────────────────────────────────────────────────────────

def test_metadata_inclui_yeast_strain_com_campos(app):
    with app.app_context():
        meta = build_metadata_json()
        names = [e["name"] for e in meta["entities"]]
        assert "yeast_strain" in names

        entity = next(e for e in meta["entities"] if e["name"] == "yeast_strain")
        field_names = [f["name"] for f in entity["fields"]]
        assert "id" in field_names
        assert "name" in field_names
        name_field = next(f for f in entity["fields"] if f["name"] == "name")
        assert name_field["type"] == "TEXT"
        assert name_field["max_length"] == 200


def test_metadata_formato_reconhecido_pelo_connection_manager(app):
    # O formato {"entities": [...]} é o mesmo que
    # core/odata/connection_manager.py::_normalize_json já reconhece
    # nativamente — valida que não inventei um formato paralelo.
    with app.app_context():
        meta = build_metadata_json()
        assert "entities" in meta
        assert meta["_source_format"] == "json"
        for entity in meta["entities"]:
            assert "name" in entity and "fields" in entity and "ui" in entity


# ── service.query_local / patch_local ───────────────────────────────────

def test_query_local_entidade_nao_exposta(app):
    with app.app_context():
        with pytest.raises(EntityNotExposedError):
            query_local("nao_existe")


def test_query_local_sem_permissao_nega(app):
    _create_user(app, "sempermissao", is_admin=False)
    with app.app_context():
        user = User.query.filter_by(username="sempermissao").first()
        with pytest.raises(PermissionDeniedError):
            query_local("yeast_strain", user=user)


def test_query_local_admin_sempre_passa(app):
    _seed_strain(app, name="Ale Yeast")
    _create_user(app, "admin2", is_admin=True)
    with app.app_context():
        user = User.query.filter_by(username="admin2").first()
        # is_admin=True -> has_permission() sempre True (mesmo padrão do resto do RBAC)
        result = query_local("yeast_strain", user=user)
        assert result["@odata.count"] >= 1
        assert any(r["name"] == "Ale Yeast" for r in result["value"])


def test_query_local_paginacao_top_skip(app):
    with app.app_context():
        for i in range(5):
            db.session.add(YeastStrain(name=f"Cepa {i}", status="disponivel"))
        db.session.commit()
        user = None  # sem permission_required checado aqui pois vamos usar admin
        admin = User(username="pgadmin", email="pgadmin@test.local", nome="X",
                     nome_completo="X", celular="119", is_admin=True, is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()

        result = query_local("yeast_strain", {"$top": 2, "$skip": 1}, user=admin)
        assert len(result["value"]) == 2
        assert result["@odata.count"] == 5


def test_query_local_filter_simples(app):
    with app.app_context():
        db.session.add(YeastStrain(name="Filtrada", status="descartada"))
        db.session.add(YeastStrain(name="Outra", status="disponivel"))
        db.session.commit()
        admin = User(username="filtadmin", email="f@test.local", nome="X",
                     nome_completo="X", celular="119", is_admin=True, is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()

        result = query_local("yeast_strain", {"$filter": "status eq 'descartada'"}, user=admin)
        assert all(r["status"] == "descartada" for r in result["value"])
        assert any(r["name"] == "Filtrada" for r in result["value"])


def test_patch_local_atualiza_registro(app):
    strain_id = _seed_strain(app, name="Original")
    with app.app_context():
        admin = User(username="patchadmin", email="p@test.local", nome="X",
                     nome_completo="X", celular="119", is_admin=True, is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()

        result = patch_local("yeast_strain", str(strain_id), {"name": "Atualizada"}, user=admin)
        assert result["name"] == "Atualizada"
        assert YeastStrain.query.get(strain_id).name == "Atualizada"


def test_patch_local_registro_inexistente(app):
    with app.app_context():
        admin = User(username="patchadmin2", email="p2@test.local", nome="X",
                     nome_completo="X", celular="119", is_admin=True, is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()
        with pytest.raises(ValueError):
            patch_local("yeast_strain", "999999", {"name": "X"}, user=admin)


# ── rotas HTTP ────────────────────────────────────────────────────────────

def test_http_metadata_exige_login(client):
    resp = client.get("/api/odata-provider/$metadata.json")
    assert resp.status_code in (302, 401)


def test_http_metadata_com_login(app, client):
    _create_user(app, "httpadmin", is_admin=True)
    _login(client, "httpadmin")
    resp = client.get("/api/odata-provider/$metadata.json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(e["name"] == "yeast_strain" for e in data["entities"])


def test_http_query_entidade_inexistente_404(app, client):
    _create_user(app, "httpadmin2", is_admin=True)
    _login(client, "httpadmin2")
    resp = client.get("/api/odata-provider/entidade_fantasma")
    assert resp.status_code == 404


def test_http_query_retorna_dados_reais(app, client):
    _seed_strain(app, name="HTTP Strain")
    _create_user(app, "httpadmin3", is_admin=True)
    _login(client, "httpadmin3")
    resp = client.get("/api/odata-provider/yeast_strain")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(r["name"] == "HTTP Strain" for r in data["value"])


def test_http_patch_atualiza_registro(app, client):
    strain_id = _seed_strain(app, name="Antes do PATCH")
    _create_user(app, "httpadmin4", is_admin=True)
    _login(client, "httpadmin4")
    resp = client.patch(f"/api/odata-provider/yeast_strain({strain_id})", json={"name": "Depois do PATCH"})
    assert resp.status_code == 200
    with app.app_context():
        assert YeastStrain.query.get(strain_id).name == "Depois do PATCH"


# ── atalho em processo (ODataConnectionManager) ──────────────────────────

def test_connection_manager_local_fetch_metadata_sem_http(app):
    from core.odata.connection_manager import ODataConnectionManager
    from model.core.odata_connection import ODataConnection

    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        assert local_conn is not None

        meta = ODataConnectionManager(local_conn).fetch_metadata()
        assert any(e["name"] == "yeast_strain" for e in meta["entities"])
        # atalho local nunca grava cache (sempre ao vivo)
        assert local_conn.metadata_cache is None


def test_connection_manager_local_query_sem_http(app):
    from core.odata.connection_manager import ODataConnectionManager
    from model.core.odata_connection import ODataConnection

    _seed_strain(app, name="Via Manager")
    with app.app_context():
        local_conn = ODataConnection.query.filter_by(is_local=True).first()
        admin = User(username="mgradmin", email="m@test.local", nome="X",
                     nome_completo="X", celular="119", is_admin=True, is_active=True)
        admin.set_password("x")
        db.session.add(admin)
        db.session.commit()
        # login real, pra current_user resolver dentro do atalho
        pass

    with app.test_request_context():
        from flask_login import login_user
        with app.app_context():
            admin = User.query.filter_by(username="mgradmin").first()
            login_user(admin)
            local_conn = ODataConnection.query.filter_by(is_local=True).first()
            result = ODataConnectionManager(local_conn).query("yeast_strain")
            assert any(r["name"] == "Via Manager" for r in result["value"])
