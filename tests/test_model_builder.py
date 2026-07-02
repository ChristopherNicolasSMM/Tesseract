"""
tests/test_model_builder.py

Cobre o Model Builder Visual (skill 06, Patch A): rascunho + campos,
filtro de FK cross-Addon (skill 02), geração real via pipeline do
CrudGen, e as rotas web.

Mesmo padrão de projeto temporário do test_phase4_crudgen.py — um
addon_smoketest_mb real em disco, para o pipeline de geração (que
escreve arquivo) ter onde escrever. `app` é escopo de módulo pelo
mesmo motivo documentado lá: redefinir um model dinamicamente a cada
teste duplicaria a Table na metadata do SQLAlchemy.
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import db
from services.core import model_builder_service as svc
from model.core.model_definition import ModelDefinition, ModelDefinitionScope, ModelDefinitionStatus
from model.core.model_field_definition import ModelFieldType
from model.core.user import User

_tmp_dir = tempfile.mkdtemp(prefix="tesseract_model_builder_test_")
_PROJECT_ROOT = Path(_tmp_dir)

_addon_dir = _PROJECT_ROOT / "addons" / "addon_smoketest_mb"
_addon_dir.mkdir(parents=True, exist_ok=True)
(_addon_dir / "addon.json").write_text(
    json.dumps({"name": "smoketest_mb", "table_prefix": "smoketestmb"}), encoding="utf-8"
)


def _cleanup_tmp_dir():
    shutil.rmtree(_tmp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def app():
    app = create_app(env="testing")
    yield app
    _cleanup_tmp_dir()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module", autouse=True)
def _use_tmp_project_root_for_http_routes(app):
    """
    A rota HTTP de geração resolve project_root a partir do app real
    (controller/core/model_builder.py:_project_root) — em produção isso
    é correto (raiz real do Tesseract), mas em teste precisa apontar
    para o mesmo diretório temporário usado pelas chamadas diretas ao
    service, senão a rota tentaria escrever dentro do próprio
    repositório clonado.
    """
    import controller.core.model_builder as controller_module

    original = controller_module._project_root
    controller_module._project_root = lambda: _PROJECT_ROOT
    yield
    controller_module._project_root = original


def _login_admin(app, client):
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@test.local", nome="Admin",
                         nome_completo="Admin", celular="0", is_admin=True, is_active=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})


# ── Service: rascunho + campos + FK ─────────────────────────────────────────

def test_criar_rascunho_e_adicionar_campos(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetMB", table_short_name="widget_mb", created_by_user_id=None,
        )
        assert definition.target_scope == ModelDefinitionScope.EXISTING_ADDON
        assert definition.status == ModelDefinitionStatus.DRAFT

        field = svc.add_field(
            definition, field_name="name", field_type=ModelFieldType.STRING,
            label_text="Nome", is_required=True, max_length=100, nullable=False,
        )
        assert field.field_name == "name"
        assert len(definition.fields) == 1


def test_fk_so_lista_tabelas_do_mesmo_addon_e_tesseract_user(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetFkTest", table_short_name="widget_fk_test", created_by_user_id=None,
        )
        candidates = {c["table_name"] for c in svc.fk_candidates(definition)}
        assert "tesseract_user" in candidates
        # Nenhuma tabela de outro Addon (ex.: brewstation) pode aparecer.
        assert not any(t.startswith("tesseract_brewstation_") for t in candidates)


def test_fk_para_tabela_de_outro_addon_e_rejeitada(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetFkReject", table_short_name="widget_fk_reject", created_by_user_id=None,
        )
        with pytest.raises(svc.ModelBuilderError):
            svc.add_field(
                definition, field_name="outro_addon_id", field_type=ModelFieldType.FOREIGN_KEY,
                label_text="Não deveria ser aceito", fk_target_table="tesseract_module_state",
            )


def test_fk_para_tesseract_user_e_aceita(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetOwner", table_short_name="widget_owner", created_by_user_id=None,
        )
        field = svc.add_field(
            definition, field_name="owner_id", field_type=ModelFieldType.FOREIGN_KEY,
            label_text="Dono", fk_target_table="tesseract_user",
        )
        assert field.fk_target_table == "tesseract_user"


def test_gerar_sem_campos_falha(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetEmpty", table_short_name="widget_empty", created_by_user_id=None,
        )
        with pytest.raises(svc.ModelBuilderError):
            svc.generate(definition.id, project_root=_PROJECT_ROOT)


# ── Geração real de ponta a ponta (uma única vez por módulo) ────────────────

@pytest.fixture(scope="module")
def generated(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="GeneratedWidget", table_short_name="generated_widget", created_by_user_id=None,
        )
        svc.add_field(definition, field_name="name", field_type=ModelFieldType.STRING,
                       label_text="Nome", is_required=True, max_length=120, nullable=False)
        svc.add_field(definition, field_name="quantity", field_type=ModelFieldType.INTEGER,
                       label_text="Quantidade", default_value="0")
        result = svc.generate(definition.id, project_root=_PROJECT_ROOT)
        yield definition.id, result


def test_geracao_escreve_model_py_e_roda_pipeline_completo(app, generated):
    definition_id, result = generated
    assert result["table_name"] == "tesseract_smoketestmb_generated_widget"
    # model.py + os 8 arquivos do pipeline do CrudGen
    assert len(result["written"]) == 9

    with app.app_context():
        definition = ModelDefinition.query.get(definition_id)
        assert definition.status == ModelDefinitionStatus.GENERATED
        assert definition.generated_at is not None


def test_geracao_pula_migration_em_testing(app, generated):
    _, result = generated
    # skill 06 + mesmo padrão do MQTT/scheduler: TESTING pula autogenerate.
    assert result["migration_message"] is None


def test_geracao_escreve_i18n(app, generated):
    definition_id, result = generated
    i18n_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "i18n" / "pt_BR.json"
    assert i18n_path.exists()
    data = json.loads(i18n_path.read_text(encoding="utf-8"))
    assert data["smoketest_mb.generated_widget.field_name"] == "Nome"
    assert data["smoketest_mb.generated_widget.field_quantity"] == "Quantidade"


def test_geracao_repetida_sem_overwrite_falha(app, generated):
    definition_id, _ = generated
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError):
            svc.generate(definition_id, project_root=_PROJECT_ROOT, overwrite=False)


# ── Rotas web ────────────────────────────────────────────────────────────

def test_tela_manage_carrega(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/model-builder/")
    assert resp.status_code == 200
    assert b"Model Builder" in resp.data


def test_fluxo_completo_via_http(app, client):
    _login_admin(app, client)

    resp = client.post(
        "/admin/model-builder/",
        data={
            "target_addon_name": "smoketest_mb",
            "target_feature_name": "",
            "model_name": "HttpWidget",
            "table_short_name": "http_widget",
        },
        follow_redirects=True,
    )
    assert b"HttpWidget" in resp.data

    with app.app_context():
        definition = ModelDefinition.query.filter_by(model_name="HttpWidget").first()
        assert definition is not None
        definition_id = definition.id

    resp = client.post(
        f"/admin/model-builder/{definition_id}/fields",
        data={
            "field_name": "title", "field_type": "string", "label_text": "Título",
            "nullable": "1", "max_length": "80", "is_listview_column": "1", "is_form_field": "1",
        },
        follow_redirects=True,
    )
    assert b"title" in resp.data

    resp = client.post(
        f"/admin/model-builder/{definition_id}/generate",
        data={},
        follow_redirects=True,
    )
    assert b"Gerado" in resp.data

    with app.app_context():
        definition = ModelDefinition.query.get(definition_id)
        assert definition.status == ModelDefinitionStatus.GENERATED
