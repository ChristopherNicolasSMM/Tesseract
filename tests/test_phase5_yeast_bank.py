"""
tests/test_phase5_yeast_bank.py

Primeiro Addon real, ponta a ponta: addon_brewstation/feature_yeast_bank
descoberto a partir de addons/ em disco, tabela criada com o prefixo
tri-nível correto, CRUD funcional via HTTP, permissões reais.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.user import User


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_admin_and_login(app, client):
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


def test_addon_brewstation_eh_descoberto_e_registrado(app):
    assert "brewstation" in app.module_manager.active_modules


def test_tabela_yeast_strain_tem_prefixo_tri_nivel_correto(app):
    with app.app_context():
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        assert YeastStrain.__tablename__ == "tesseract_brewstation_yeastbank_strain"


def test_permissoes_de_yeast_strains_existem(app):
    from model.core.permission import Permission

    with app.app_context():
        nomes = {p.name for p in Permission.query.all()}
        for action in ("list", "detail", "create", "update", "trash", "restore", "delete_permanent"):
            assert f"yeast_strains.{action}" in nomes
        # Camada 2 — ação de negócio específica desta cepa
        # "recalculate_viability" foi movida pra yeast_bank_items
        # (onde a ação de fato opera) — ver tests/test_viability_engine.py
        assert "yeast_bank_items.recalculate_viability" in nomes


def test_crud_completo_via_http(app, client):
    _create_admin_and_login(app, client)

    resp = client.post(
        "/api/brewstation/yeast-strains/",
        json={"name": "US-05", "family": "Ale", "supplier": "Fermentis"},
    )
    assert resp.status_code == 201
    item_id = resp.get_json()["item"]["id"]

    resp = client.get("/api/brewstation/yeast-strains/")
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) == 1

    resp = client.get(f"/api/brewstation/yeast-strains/{item_id}")
    assert resp.status_code == 200
    assert resp.get_json()["item"]["name"] == "US-05"

    resp = client.put(
        f"/api/brewstation/yeast-strains/{item_id}",
        json={"family": "Lager"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["item"]["family"] == "Lager"

    resp = client.post(f"/api/brewstation/yeast-strains/{item_id}/trash")
    assert resp.status_code == 200

    # depois de trash, some da listagem padrão (is_deleted filtrado)
    resp = client.get("/api/brewstation/yeast-strains/")
    assert len(resp.get_json()["items"]) == 0

    resp = client.post(f"/api/brewstation/yeast-strains/{item_id}/restore")
    assert resp.status_code == 200

    resp = client.get("/api/brewstation/yeast-strains/")
    assert len(resp.get_json()["items"]) == 1


def test_usuario_sem_permissao_nao_consegue_criar(app, client):
    with app.app_context():
        user = User(
            username="comum", email="comum@test.local",
            nome="Comum", nome_completo="Usuário Comum", celular="11988888888",
            is_admin=False, is_active=True,
        )
        user.set_password("senha123")
        db.session.add(user)
        db.session.commit()

    client.post("/api/auth/login", json={"username": "comum", "password": "senha123"})

    resp = client.post("/api/brewstation/yeast-strains/", json={"name": "US-05"})
    assert resp.status_code == 403
