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


# ── list_existing_addons() — select box em vez de texto livre (BACKLOG.md) ──

def test_list_existing_addons_encontra_addon_de_teste():
    addons = svc.list_existing_addons(_PROJECT_ROOT)
    by_name = {a["name"]: a for a in addons}
    assert "smoketest_mb" in by_name


def test_list_existing_addons_le_features_do_addon():
    feature_dir = _addon_dir / "features" / "feature_smoketest_mb_sub"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature.json").write_text(
        json.dumps({"name": "smoketest_mb_sub", "label": "Sub Feature de Teste"}),
        encoding="utf-8",
    )
    try:
        addons = svc.list_existing_addons(_PROJECT_ROOT)
        by_name = {a["name"]: a for a in addons}
        feature_names = {f["name"] for f in by_name["smoketest_mb"]["features"]}
        assert "smoketest_mb_sub" in feature_names
    finally:
        shutil.rmtree(feature_dir, ignore_errors=True)


def test_list_existing_addons_ignora_pasta_sem_manifesto(tmp_path):
    (tmp_path / "addons" / "addon_incompleto").mkdir(parents=True)
    assert svc.list_existing_addons(tmp_path) == []


def test_list_existing_addons_pasta_addons_inexistente(tmp_path):
    assert svc.list_existing_addons(tmp_path / "nao_existe") == []


def test_tela_manage_lista_addons_no_select(app, client):
    _login_admin(app, client)
    resp = client.get("/admin/model-builder/")
    assert resp.status_code == 200
    # A tela real usa addons/ do projeto real (current_app.root_path),
    # não o _PROJECT_ROOT de teste — só confirma que o <select> existe
    # e não quebrou a renderização.
    assert b'id="addonSelectExisting"' in resp.data
    assert b'id="addonInputNew"' in resp.data


# ── update_field() / preview_model_source() (achado real, ver BACKLOG.md) ──

def test_update_field_altera_valores_e_preserva_ordem(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetEdit", table_short_name="widget_edit", created_by_user_id=None,
        )
        f1 = svc.add_field(definition, field_name="nome", field_type=ModelFieldType.STRING,
                            label_text="Nome", max_length=50)
        svc.add_field(definition, field_name="ativo", field_type=ModelFieldType.BOOLEAN, label_text="Ativo")

        updated = svc.update_field(
            f1.id, field_name="nome", field_type=ModelFieldType.STRING,
            label_text="Nome Completo", max_length=120, is_required=True,
        )
        assert updated.label_text == "Nome Completo"
        assert updated.max_length == 120
        assert updated.is_required is True

        definition = ModelDefinition.query.get(definition.id)
        assert [f.field_name for f in definition.fields] == ["nome", "ativo"]


def test_update_field_campo_inexistente_falha(app):
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError):
            svc.update_field(999999, field_name="x", field_type=ModelFieldType.STRING, label_text="X")


def test_update_field_fk_invalida_rejeitada(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetEditFk", table_short_name="widget_edit_fk", created_by_user_id=None,
        )
        f = svc.add_field(definition, field_name="nome", field_type=ModelFieldType.STRING,
                           label_text="Nome", max_length=50)
        with pytest.raises(svc.ModelBuilderError):
            svc.update_field(
                f.id, field_name="nome", field_type=ModelFieldType.FOREIGN_KEY,
                label_text="Nome", fk_target_table="tesseract_outro_addon_qualquer",
            )


def test_preview_model_source_reflete_campos_atuais(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetPreview", table_short_name="widget_preview", created_by_user_id=None,
        )
        svc.add_field(definition, field_name="titulo", field_type=ModelFieldType.STRING,
                       label_text="Título", max_length=80, is_required=True)

        source = svc.preview_model_source(definition, project_root=_PROJECT_ROOT)
        assert "class WidgetPreview(db.Model)" in source
        assert "titulo = db.Column(" in source
        assert '__tablename__ = "widget_preview"' in source
        assert '@required("titulo")' in source


def test_preview_model_source_muda_ao_editar_campo(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetPreview2", table_short_name="widget_preview2", created_by_user_id=None,
        )
        f = svc.add_field(definition, field_name="apelido", field_type=ModelFieldType.STRING,
                           label_text="Apelido", max_length=20)
        before = svc.preview_model_source(definition, project_root=_PROJECT_ROOT)
        assert "@max_length(\"apelido\", 20)" in before

        svc.update_field(f.id, field_name="apelido", field_type=ModelFieldType.STRING,
                          label_text="Apelido", max_length=200)
        definition = ModelDefinition.query.get(definition.id)
        after = svc.preview_model_source(definition, project_root=_PROJECT_ROOT)
        assert "@max_length(\"apelido\", 200)" in after
        assert "@max_length(\"apelido\", 20)" not in after


# ── Rota web: editar campo + preview na tela ────────────────────────────────

def test_editar_campo_pela_tela(app, client):
    _login_admin(app, client)
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetHttpEdit", table_short_name="widget_http_edit", created_by_user_id=None,
        )
        f = svc.add_field(definition, field_name="qtd", field_type=ModelFieldType.INTEGER, label_text="Quantidade")
        definition_id, field_id = definition.id, f.id

    resp = client.post(
        f"/admin/model-builder/{definition_id}/fields/{field_id}/edit",
        data={
            "field_name": "qtd", "field_type": "integer", "label_text": "Quantidade Total",
            "is_required": "1", "is_listview_column": "1", "is_form_field": "1",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Quantidade Total".encode() in resp.data

    with app.app_context():
        from model.core.model_field_definition import ModelFieldDefinition
        updated = ModelFieldDefinition.query.get(field_id)
        assert updated.label_text == "Quantidade Total"
        assert updated.is_required is True


def test_tela_detail_mostra_preview_e_guia_de_anotacoes(app, client):
    _login_admin(app, client)
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetHttpPreview", table_short_name="widget_http_preview", created_by_user_id=None,
        )
        svc.add_field(definition, field_name="cor", field_type=ModelFieldType.STRING, label_text="Cor", max_length=30)
        definition_id = definition.id

    resp = client.get(f"/admin/model-builder/{definition_id}")
    assert resp.status_code == 200
    assert b"class WidgetHttpPreview(db.Model)" in resp.data
    assert b"Guia de Anota" in resp.data
    assert b"js-edit-field" in resp.data


# ── Campo tipo JSON + sub-campos (documentação, não sub-tabela real) ────────

def test_add_field_json_com_sub_campos(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetJson", table_short_name="widget_json", created_by_user_id=None,
        )
        schema = [
            {"name": "recipe", "type": "object", "children": [
                {"name": "name", "type": "string"},
                {"name": "abv", "type": "float"},
            ]},
        ]
        field = svc.add_field(
            definition, field_name="payload", field_type=ModelFieldType.JSON,
            label_text="Payload", json_schema=schema,
        )
        assert field.field_type == "json"
        assert field.json_schema == schema


def test_update_field_json_schema_e_limpo_ao_trocar_de_tipo(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetJsonClear", table_short_name="widget_json_clear", created_by_user_id=None,
        )
        field = svc.add_field(
            definition, field_name="payload", field_type=ModelFieldType.JSON,
            label_text="Payload", json_schema=[{"name": "x", "type": "string"}],
        )
        svc.update_field(
            field.id, field_name="payload", field_type=ModelFieldType.STRING,
            label_text="Payload", json_schema=[{"name": "x", "type": "string"}],
        )
        assert field.field_type == "string"
        assert field.json_schema is None  # não faz sentido guardar schema pra um campo que não é mais json


def test_preview_mostra_comentario_de_sub_campos(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetJsonPreview", table_short_name="widget_json_preview", created_by_user_id=None,
        )
        svc.add_field(
            definition, field_name="payload", field_type=ModelFieldType.JSON,
            label_text="Payload",
            json_schema=[{"name": "recipe", "type": "object", "children": [{"name": "name", "type": "string"}]}],
        )
        preview = svc.preview_model_source(definition, project_root=_PROJECT_ROOT)
        assert "sub-campos esperados" in preview
        assert "recipe" in preview
        assert "db.JSON" in preview


# ── Reposicionar campos (drag-and-drop, order_index já existia) ─────────────

def test_reorder_fields_atualiza_order_index(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetReorder", table_short_name="widget_reorder", created_by_user_id=None,
        )
        f1 = svc.add_field(definition, field_name="a", field_type=ModelFieldType.STRING, label_text="A")
        f2 = svc.add_field(definition, field_name="b", field_type=ModelFieldType.STRING, label_text="B")
        f3 = svc.add_field(definition, field_name="c", field_type=ModelFieldType.STRING, label_text="C")
        assert [f.order_index for f in [f1, f2, f3]] == [0, 1, 2]

        svc.reorder_fields(definition.id, [f3.id, f1.id, f2.id])

        db.session.refresh(f1)
        db.session.refresh(f2)
        db.session.refresh(f3)
        assert f3.order_index == 0
        assert f1.order_index == 1
        assert f2.order_index == 2

        # A ordenação real do relationship (ModelDefinition.fields,
        # order_by=order_index) já reflete sem precisar de mais nada.
        db.session.refresh(definition)
        assert [f.field_name for f in definition.fields] == ["c", "a", "b"]


def test_reorder_fields_pela_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="WidgetReorderHttp", table_short_name="widget_reorder_http", created_by_user_id=None,
        )
        f1 = svc.add_field(definition, field_name="a", field_type=ModelFieldType.STRING, label_text="A")
        f2 = svc.add_field(definition, field_name="b", field_type=ModelFieldType.STRING, label_text="B")
        definition_id, f1_id, f2_id = definition.id, f1.id, f2.id

    resp = client.post(
        f"/admin/model-builder/{definition_id}/fields/reorder",
        json={"field_ids": [f2_id, f1_id]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    with app.app_context():
        from model.core.model_field_definition import ModelFieldDefinition
        assert ModelFieldDefinition.query.get(f2_id).order_index == 0
        assert ModelFieldDefinition.query.get(f1_id).order_index == 1


# -- Inferencia de campo aninhado (Playground -> Model Builder) --------------
# Objeto/array-de-objeto agora vira tabela filha de verdade (skill 06,
# decisao em conversa/BACKLOG.md) -- so array de valores simples (sem
# objeto) continua virando `json` de documentacao.

def test_infer_field_type_objeto_vira_table():
    from services.core.playground_service import _infer_field_type

    assert _infer_field_type({"name": "x"}) == "table"


def test_infer_field_type_array_de_objetos_vira_table():
    from services.core.playground_service import _infer_field_type

    assert _infer_field_type([{"name": "x"}]) == "table"


def test_infer_field_type_array_de_valores_simples_continua_json():
    from services.core.playground_service import _infer_field_type

    assert _infer_field_type(["ipa", "lager"]) == "json"


def test_infer_fields_from_json_objeto_aninhado_vira_relacao_1_para_1():
    from services.core import playground_service as pg_svc

    response = {
        "brewDate": 1756090800000,
        "recipe": {"name": "New Weissnbier", "abv": 5.2},
        "status": "Completed",
    }
    fields = pg_svc.infer_fields_from_json(response)
    by_name = {f["field_name"]: f for f in fields}

    assert by_name["recipe"]["field_type"] == "table"
    assert by_name["recipe"]["relation"]["relation_type"] == "one_to_one"
    child_by_name = {c["field_name"]: c for c in by_name["recipe"]["relation"]["child_fields"]}
    assert child_by_name["name"]["field_type"] == "string"
    assert child_by_name["abv"]["field_type"] == "float"
    assert by_name["status"]["field_type"] == "string"


def test_infer_fields_from_json_array_de_objetos_vira_relacao_1_para_n():
    from services.core import playground_service as pg_svc

    response = [
        {"id": 1, "itens": [{"produto": "Malte", "qtd": 2}, {"produto": "Lupulo", "qtd": 1}]},
        {"id": 2, "itens": [{"produto": "Levedura", "qtd": 1}]},
    ]
    fields = pg_svc.infer_fields_from_json(response)
    by_name = {f["field_name"]: f for f in fields}

    assert by_name["itens"]["field_type"] == "table"
    assert by_name["itens"]["relation"]["relation_type"] == "one_to_many"
    child_names = {c["field_name"] for c in by_name["itens"]["relation"]["child_fields"]}
    assert child_names == {"produto", "qtd"}


def test_infer_fields_from_json_array_de_valores_simples_continua_json():
    from services.core import playground_service as pg_svc

    response = {"tags": ["ipa", "lupulado"]}
    fields = pg_svc.infer_fields_from_json(response)
    by_name = {f["field_name"]: f for f in fields}

    assert by_name["tags"]["field_type"] == "json"
    assert by_name["tags"].get("relation") is None


def test_infer_table_relation_cap_de_1_nivel_no_filho():
    """Dentro do filho, um dict/list aninhado de novo NAO vira neto --
    cai de volta pra `json` de documentacao (cap decidido em conversa)."""
    from services.core.playground_service import _infer_table_relation

    relation = _infer_table_relation({"nome": "x", "endereco": {"rua": "y"}})
    child_by_name = {c["field_name"]: c for c in relation["child_fields"]}
    assert child_by_name["endereco"]["field_type"] == "json"


def test_infer_json_schema_ainda_funciona_pra_array_de_valores_simples_dentro_de_um_objeto():
    from services.core.playground_service import _infer_json_schema

    schema = _infer_json_schema(["a", "b"])
    assert schema is None  # array de valor simples nao tem "sub-campo" nomeado


def test_create_model_definition_from_playground_com_relacao_cria_filho(app):
    from services.core import playground_service as pg_svc
    from model.core.playground_request import PlaygroundRequest

    with app.app_context():
        record = PlaygroundRequest(
            kind="http", name="teste", http_method="GET", url="https://x",
            last_response_json={
                "brewDate": 1756090800000,
                "recipe": {"name": "New Weissnbier"},
            },
            last_status_code=200,
        )
        db.session.add(record)
        db.session.commit()

        definition = pg_svc.create_model_definition_from_playground(
            record.id, target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="Batch", table_short_name="batch", created_by_user_id=None,
            project_root=_PROJECT_ROOT,
        )

        table_field = next(f for f in definition.fields if f.field_type == "table")
        assert table_field.field_name == "recipe"
        child = ModelDefinition.query.get(table_field.child_model_definition_id)
        assert child.model_name == "Recipe"
        assert child.parent_relation_type == "one_to_one"
        assert child.parent_fk_column_name == "batch_id"
        child_field_names = {f.field_name for f in child.fields if f.field_type != "foreign_key"}
        assert child_field_names == {"name"}
        # FK de volta pro pai ja foi criada no filho
        fk_field = next(f for f in child.fields if f.field_type == "foreign_key")
        assert fk_field.field_name == "batch_id"
        assert "batch" in fk_field.fk_target_table


# ── Geração real com tabela filha (skill 06 — relacionamento de verdade) ────

@pytest.fixture(scope="module")
def generated_with_child(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="Pedido", table_short_name="pedido", created_by_user_id=None,
        )
        svc.add_field(definition, field_name="numero", field_type=ModelFieldType.STRING,
                       label_text="Número", is_required=True, max_length=30, nullable=False)
        svc.add_table_field(
            definition, field_name="itens", label_text="Itens do Pedido",
            child_model_name="PedidoItem", child_table_short_name="pedido_item",
            relation_type="one_to_many", project_root=_PROJECT_ROOT,
        )
        table_field = next(f for f in definition.fields if f.field_type == "table")
        child_id = table_field.child_model_definition_id
        child = ModelDefinition.query.get(child_id)
        svc.add_field(child, field_name="produto", field_type=ModelFieldType.STRING,
                       label_text="Produto", is_required=True, max_length=100, nullable=False)
        svc.add_field(child, field_name="quantidade", field_type=ModelFieldType.INTEGER,
                       label_text="Quantidade", default_value="1")

        result = svc.generate(definition.id, project_root=_PROJECT_ROOT)
        yield definition.id, child_id, result


def test_geracao_com_tabela_filha_escreve_pai_e_filho(app, generated_with_child):
    definition_id, child_id, result = generated_with_child
    assert result["children_generated"] == ["tesseract_smoketestmb_pedido_item"]
    # model.py do pai + 8 arquivos do CrudGen do pai + model.py do filho + 8 do CrudGen do filho
    assert len(result["written"]) == 18

    with app.app_context():
        definition = ModelDefinition.query.get(definition_id)
        child = ModelDefinition.query.get(child_id)
        assert definition.status == ModelDefinitionStatus.GENERATED
        assert child.status == ModelDefinitionStatus.GENERATED
        assert child.migration_revision == definition.migration_revision  # mesma migration, uma só


def test_geracao_com_tabela_filha_child_model_py_tem_fk_pro_pai(app, generated_with_child):
    _, child_id, _ = generated_with_child
    child_model_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "root" / "model" / "pedido_item.py"
    content = child_model_path.read_text(encoding="utf-8")
    assert "pedido_id" in content
    assert "db.ForeignKey" in content
    assert "tesseract_smoketestmb_pedido" in content


def test_geracao_com_tabela_filha_parent_model_py_tem_relationship(app, generated_with_child):
    parent_model_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "root" / "model" / "pedido.py"
    content = parent_model_path.read_text(encoding="utf-8")
    assert "itens = db.relationship(" in content
    assert '"PedidoItem"' in content
    assert "uselist=False" not in content  # 1:N não limita a 1


def test_geracao_com_tabela_filha_injeta_master_detail_no_detail_do_pai(app, generated_with_child):
    detail_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "root" / "templates" / "pedidos" / "detail.html"
    content = detail_path.read_text(encoding="utf-8")
    assert "model-builder:master-detail" in content
    assert "Itens do Pedido" in content
    assert "item.itens" in content
    assert "pedido_items.manage" in content


def test_geracao_com_tabela_filha_um_para_um_usa_uselist_false(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="Fatura", table_short_name="fatura", created_by_user_id=None,
        )
        svc.add_field(definition, field_name="numero", field_type=ModelFieldType.STRING, label_text="Número")
        svc.add_table_field(
            definition, field_name="endereco", label_text="Endereço de Cobrança",
            child_model_name="EnderecoCobranca", child_table_short_name="endereco_cobranca",
            relation_type="one_to_one", project_root=_PROJECT_ROOT,
        )
        table_field = next(f for f in definition.fields if f.field_type == "table")
        child = ModelDefinition.query.get(table_field.child_model_definition_id)
        svc.add_field(child, field_name="rua", field_type=ModelFieldType.STRING, label_text="Rua")

        svc.generate(definition.id, project_root=_PROJECT_ROOT)

    parent_model_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "root" / "model" / "fatura.py"
    content = parent_model_path.read_text(encoding="utf-8")
    assert "uselist=False" in content

    child_model_path = _PROJECT_ROOT / "addons" / "addon_smoketest_mb" / "root" / "model" / "endereco_cobranca.py"
    child_content = child_model_path.read_text(encoding="utf-8")
    assert "unique=True" in child_content  # FK com unique=True garante 1:1 de verdade


# ── Regras da tabela filha (cap de 1 nível, validações) ──────────────────────

def test_add_table_field_bloqueado_em_quem_ja_e_filho(app):
    with app.app_context():
        parent = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="Nivel1", table_short_name="nivel1", created_by_user_id=None,
        )
        field = svc.add_table_field(
            parent, field_name="filhos", label_text="Filhos",
            child_model_name="Nivel2", child_table_short_name="nivel2",
            relation_type="one_to_many", project_root=_PROJECT_ROOT,
        )
        child = ModelDefinition.query.get(field.child_model_definition_id)

        with pytest.raises(svc.ModelBuilderError, match="1 nível"):
            svc.add_table_field(
                child, field_name="netos", label_text="Netos",
                child_model_name="Nivel3", child_table_short_name="nivel3",
                relation_type="one_to_many", project_root=_PROJECT_ROOT,
            )


def test_add_field_rejeita_tipo_table_direto(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="RejeitaTable", table_short_name="rejeita_table", created_by_user_id=None,
        )
        with pytest.raises(svc.ModelBuilderError):
            svc.add_field(definition, field_name="x", field_type="table", label_text="X")


def test_remove_field_table_apaga_o_filho_junto(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="ApagaFilho", table_short_name="apaga_filho", created_by_user_id=None,
        )
        field = svc.add_table_field(
            definition, field_name="filhos", label_text="Filhos",
            child_model_name="ApagaFilhoItem", child_table_short_name="apaga_filho_item",
            relation_type="one_to_many", project_root=_PROJECT_ROOT,
        )
        child_id = field.child_model_definition_id

        svc.remove_field(field.id)

        assert ModelDefinition.query.get(child_id) is None


def test_add_table_field_pela_rota_web(app, client):
    _login_admin(app, client)
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="ViaTela", table_short_name="via_tela", created_by_user_id=None,
        )
        definition_id = definition.id

    resp = client.post(
        f"/admin/model-builder/{definition_id}/fields/table",
        data={
            "field_name": "itens", "label_text": "Itens", "child_model_name": "ViaTelaItem",
            "child_table_short_name": "via_tela_item", "relation_type": "one_to_many",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"tabela filha" in resp.data.lower()

    with app.app_context():
        definition = ModelDefinition.query.get(definition_id)
        table_field = next(f for f in definition.fields if f.field_type == "table")
        assert table_field.child_model_definition_id is not None


def test_tela_manage_so_lista_definicoes_de_topo(app, client):
    _login_admin(app, client)
    with app.app_context():
        parent = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="TopoVisivel", table_short_name="topo_visivel", created_by_user_id=None,
        )
        field = svc.add_table_field(
            parent, field_name="filhos", label_text="Filhos",
            child_model_name="FilhoInvisivelNaLista", child_table_short_name="filho_invisivel_lista",
            relation_type="one_to_many", project_root=_PROJECT_ROOT,
        )

    resp = client.get("/admin/model-builder/")
    assert b"TopoVisivel" in resp.data
    assert b"FilhoInvisivelNaLista" not in resp.data


def test_tela_detail_do_pai_mostra_arvore_do_filho(app, client):
    _login_admin(app, client)
    with app.app_context():
        parent = svc.create_draft(
            target_addon_name="smoketest_mb", target_feature_name=None,
            model_name="ArvoreNaTela", table_short_name="arvore_na_tela", created_by_user_id=None,
        )
        field = svc.add_table_field(
            parent, field_name="filhos", label_text="Filhos Visiveis",
            child_model_name="FilhoNaArvore", child_table_short_name="filho_na_arvore",
            relation_type="one_to_many", project_root=_PROJECT_ROOT,
        )
        parent_id = parent.id

    resp = client.get(f"/admin/model-builder/{parent_id}")
    assert resp.status_code == 200
    assert b"FilhoNaArvore" in resp.data
    assert b"Filhos Visiveis" in resp.data or "Filhos Visiveis".encode("utf-8") in resp.data
