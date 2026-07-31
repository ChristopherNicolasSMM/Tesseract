"""
tests/test_fase10_patch1_schema.py

Fase 10, Patch 1 — fundação de schema (Ações + Dados + substituição de
tela CrudGen). Cobertura apenas de schema/seed/anotação — sem endpoint
(Patch 2/3) nem UI de editor (Patch 4/5). Ver
docs/skills/16-designer-acoes-e-dados.md (a formalizar) e
BACKLOG.md, Fase 10.
"""
import pytest

from core.app_factory import create_app
from core.db import db
from model.core.odata_connection import ODataConnection
from model.core.designer_page import DesignerPage
from model.core.designer_data_action import DesignerDataAction
from core.odata_local_seed import ensure_local_odata_connection, LOCAL_CONNECTION_NAME
from annotations import odata_expose, get_odata_expose_meta


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


# ── ODataConnection.is_local ─────────────────────────────────────────────

def test_odata_connection_is_local_default_false(app):
    with app.app_context():
        conn = ODataConnection(name="Externa", base_url="https://exemplo.com/odata")
        db.session.add(conn)
        db.session.commit()
        assert conn.is_local is False
        assert conn.to_dict()["is_local"] is False


def test_seed_conexao_local_idempotente(app):
    with app.app_context():
        first = ensure_local_odata_connection()
        assert first is not None
        assert first.name == LOCAL_CONNECTION_NAME
        assert first.is_local is True

        # roda de novo — não pode duplicar (mesmo padrão de seed_config)
        second = ensure_local_odata_connection()
        assert second.id == first.id
        assert ODataConnection.query.filter_by(is_local=True).count() == 1


def test_seed_conexao_local_ja_roda_no_boot(app):
    # create_app(env="testing") já passa por create_all_pending_tables()
    # normal (não é contexto "flask db ..."), então o seed já deve ter
    # rodado sozinho, sem chamada manual.
    with app.app_context():
        assert ODataConnection.query.filter_by(is_local=True).count() == 1


# ── DesignerPage — campos de substituição ────────────────────────────────

def test_designer_page_replaces_fields_default(app):
    with app.app_context():
        page = DesignerPage(name="Tela X", slug="tela-x")
        db.session.add(page)
        db.session.commit()
        assert page.replaces_entity_key is None
        assert page.replaces_view is None
        assert page.replace_in_menu is False


def test_designer_page_replaces_fields_preenchidos(app):
    with app.app_context():
        page = DesignerPage(
            name="Yeast Strains customizada", slug="yeast-strains-custom",
            replaces_entity_key="yeast_strain", replaces_view="manage",
            replace_in_menu=True,
        )
        db.session.add(page)
        db.session.commit()

        d = page.to_dict()
        assert d["replaces_entity_key"] == "yeast_strain"
        assert d["replaces_view"] == "manage"
        assert d["replace_in_menu"] is True


# ── DesignerDataAction ────────────────────────────────────────────────────

def test_designer_data_action_cria_apontando_para_conexao_local(app):
    with app.app_context():
        local_conn = ensure_local_odata_connection()
        action = DesignerDataAction(
            name="Listar Yeast Strains", connection_id=local_conn.id,
            entity_name="yeast_strain", operation="query",
        )
        db.session.add(action)
        db.session.commit()

        assert action.id is not None
        assert action.operation == "query"
        assert action.static_params in (None, {})
        assert action.permission_required is None
        assert action.connection.is_local is True


def test_designer_data_action_nome_unico(app):
    with app.app_context():
        local_conn = ensure_local_odata_connection()
        db.session.add(DesignerDataAction(
            name="Duplicada", connection_id=local_conn.id,
            entity_name="yeast_strain",
        ))
        db.session.commit()

        db.session.add(DesignerDataAction(
            name="Duplicada", connection_id=local_conn.id,
            entity_name="yeast_strain",
        ))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_designer_data_action_to_dict(app):
    with app.app_context():
        local_conn = ensure_local_odata_connection()
        action = DesignerDataAction(
            name="Ação Teste", description="Descrição de teste",
            connection_id=local_conn.id, entity_name="yeast_strain",
            operation="update", static_params={"$filter": "status eq 'ativo'"},
            permission_required="yeast_strains.update",
        )
        db.session.add(action)
        db.session.commit()

        d = action.to_dict()
        assert d["name"] == "Ação Teste"
        assert d["operation"] == "update"
        assert d["static_params"] == {"$filter": "status eq 'ativo'"}
        assert d["permission_required"] == "yeast_strains.update"


# ── @odata_expose ──────────────────────────────────────────────────────────

def test_odata_expose_marca_entidade():
    @odata_expose("yeast_strain", permission_required="yeast_strains.list")
    class _FakeModel:
        pass

    meta = get_odata_expose_meta(_FakeModel)
    assert meta == {"entity_name": "yeast_strain", "permission_required": "yeast_strains.list"}


def test_odata_expose_ausente_retorna_none():
    class _OutroFakeModel:
        pass

    assert get_odata_expose_meta(_OutroFakeModel) is None


def test_odata_expose_permission_required_opcional():
    @odata_expose("material")
    class _FakeModelSemPermissao:
        pass

    meta = get_odata_expose_meta(_FakeModelSemPermissao)
    assert meta["entity_name"] == "material"
    assert meta["permission_required"] is None
