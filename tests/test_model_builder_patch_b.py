"""
tests/test_model_builder_patch_b.py

Cobre o Patch B da skill 06: target_scope "new_addon"/"new_feature" —
scaffold completo de pastas (skill 01) + manifesto (skill 03) + docs
stub (skill 04), e a integração com a skill 09 (auto-descoberta —
addon.py/feature.py gerados não escrevem register_models/
register_routes/get_transactions/get_features nenhum).

Mesmo padrão de projeto temporário do test_model_builder.py — só que
aqui o próprio Addon/Feature TAMBÉM é escrito pelo teste (scaffold
completo do zero), não só o addon.json.
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

_tmp_dir = tempfile.mkdtemp(prefix="tesseract_model_builder_patchb_test_")
_PROJECT_ROOT = Path(_tmp_dir)


def _cleanup_tmp_dir():
    shutil.rmtree(_tmp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def app():
    app = create_app(env="testing")
    yield app
    _cleanup_tmp_dir()


# ── Validação do manifest_draft_json ────────────────────────────────────────

def test_criar_draft_new_addon_sem_label_falha(app):
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError, match="Label"):
            svc.create_draft(
                target_addon_name="semlabel", target_feature_name=None,
                model_name="Widget", table_short_name="widget", created_by_user_id=None,
                is_new_addon=True, manifest_draft={"description": "x", "author": "x"},
            )


def test_criar_draft_new_addon_sem_author_falha(app):
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError, match="Author"):
            svc.create_draft(
                target_addon_name="semauthor", target_feature_name=None,
                model_name="Widget", table_short_name="widget", created_by_user_id=None,
                is_new_addon=True, manifest_draft={"label": "X", "description": "x"},
            )


def test_criar_draft_new_addon_table_prefix_longo_demais_falha(app):
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError, match="15"):
            svc.create_draft(
                target_addon_name="um_nome_de_addon_bem_comprido_demais",
                target_feature_name=None,
                model_name="Widget", table_short_name="widget", created_by_user_id=None,
                is_new_addon=True,
                manifest_draft={"label": "X", "description": "x", "author": "x"},
            )


def test_criar_draft_new_feature_suffix_longo_demais_falha(app):
    with app.app_context():
        with pytest.raises(svc.ModelBuilderError, match="12"):
            svc.create_draft(
                target_addon_name="brewstation", target_feature_name="minha_feature_nova",
                model_name="Widget", table_short_name="widget", created_by_user_id=None,
                is_new_feature=True,
                manifest_draft={
                    "label": "X", "description": "x",
                    "table_prefix_suffix": "um_sufixo_bem_comprido",
                },
            )


def test_criar_draft_new_addon_valido_ok(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="patchbaddon", target_feature_name=None,
            model_name="Widget", table_short_name="widget", created_by_user_id=None,
            is_new_addon=True,
            manifest_draft={"label": "Patch B Addon", "description": "Addon de teste do Patch B", "author": "Testes"},
        )
        assert definition.target_scope == ModelDefinitionScope.NEW_ADDON
        assert definition.manifest_draft_json["label"] == "Patch B Addon"


# ── Scaffold + geração real de Addon novo ───────────────────────────────────

@pytest.fixture(scope="module")
def generated_new_addon(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="scaffoldedaddon", target_feature_name=None,
            model_name="FirstWidget", table_short_name="first_widget", created_by_user_id=None,
            is_new_addon=True,
            manifest_draft={
                "label": "Scaffolded Addon",
                "description": "Addon gerado do zero pelo Patch B, com o primeiro Model.",
                "author": "Testes Patch B",
            },
        )
        svc.add_field(definition, field_name="name", field_type=ModelFieldType.STRING,
                       label_text="Nome", is_required=True, max_length=100, nullable=False)
        result = svc.generate(definition.id, project_root=_PROJECT_ROOT)
        yield definition.id, result


def test_scaffold_new_addon_cria_estrutura_completa(generated_new_addon):
    addon_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon"

    assert (addon_dir / "__init__.py").exists()
    assert (addon_dir / "addon.json").exists()
    assert (addon_dir / "addon.py").exists()
    assert (addon_dir / "root" / "__init__.py").exists()
    assert (addon_dir / "root" / "model" / "__init__.py").exists()
    assert (addon_dir / "root" / "model" / "first_widget.py").exists()
    assert (addon_dir / "root" / "controller" / "__init__.py").exists()
    assert (addon_dir / "root" / "services" / "__init__.py").exists()
    assert (addon_dir / "root" / "api" / "routes" / "__init__.py").exists()
    assert (addon_dir / "i18n" / "pt_BR.json").exists()
    assert (addon_dir / "static").is_dir()
    assert (addon_dir / "docs" / "technical" / "01-visao-geral.md").exists()
    assert (addon_dir / "docs" / "manual" / "01-introducao.md").exists()


def test_scaffold_new_addon_manifesto_correto(generated_new_addon):
    addon_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon"
    manifest = json.loads((addon_dir / "addon.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "scaffoldedaddon"
    assert manifest["table_prefix"] == "scaffoldedaddon"
    assert manifest["label"] == "Scaffolded Addon"
    assert manifest["author"] == "Testes Patch B"
    assert manifest["default_locale"] == "pt_BR"


def test_scaffold_new_addon_py_nao_sobrescreve_metodos_de_descoberta(generated_new_addon):
    """
    Skill 09: addon.py gerado pelo Patch B não deve escrever
    register_models/register_routes/get_transactions/get_features —
    auto-descoberta resolve tudo sozinha.
    """
    addon_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon"
    content = (addon_dir / "addon.py").read_text(encoding="utf-8")
    assert "def register_models" not in content
    assert "def register_routes" not in content
    assert "def get_transactions" not in content
    assert "def get_features" not in content
    assert "class AddonScaffoldedaddon(AddonBase):" in content


def test_scaffold_new_addon_docs_stub_preenchido(generated_new_addon):
    addon_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon"
    tech = (addon_dir / "docs" / "technical" / "01-visao-geral.md").read_text(encoding="utf-8")
    manual = (addon_dir / "docs" / "manual" / "01-introducao.md").read_text(encoding="utf-8")
    assert "Addon gerado do zero pelo Patch B" in tech
    assert "Addon gerado do zero pelo Patch B" in manual
    assert "Scaffolded Addon" in tech


def test_geracao_new_addon_status_e_tabela(app, generated_new_addon):
    definition_id, result = generated_new_addon
    assert result["scaffolded_new_module"] is True
    assert result["table_name"] == "tesseract_scaffoldedaddon_first_widget"
    with app.app_context():
        definition = ModelDefinition.query.get(definition_id)
        assert definition.status == ModelDefinitionStatus.GENERATED


def test_scaffold_new_addon_ja_existente_falha(app, generated_new_addon):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="scaffoldedaddon", target_feature_name=None,
            model_name="SecondWidget", table_short_name="second_widget", created_by_user_id=None,
            is_new_addon=True,
            manifest_draft={"label": "X", "description": "y", "author": "z"},
        )
        svc.add_field(definition, field_name="name", field_type=ModelFieldType.STRING, label_text="Nome")
        with pytest.raises(svc.ModelBuilderError, match="já existe"):
            svc.generate(definition.id, project_root=_PROJECT_ROOT)


# ── Scaffold + geração real de Feature nova (dentro do Addon já criado acima) ─

@pytest.fixture(scope="module")
def generated_new_feature(app, generated_new_addon):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="scaffoldedaddon", target_feature_name="nova_feature",
            model_name="FeatureWidget", table_short_name="feature_widget", created_by_user_id=None,
            is_new_feature=True,
            manifest_draft={
                "label": "Nova Feature",
                "description": "Feature gerada do zero pelo Patch B, dentro de um Addon já existente.",
            },
        )
        svc.add_field(definition, field_name="name", field_type=ModelFieldType.STRING,
                       label_text="Nome", nullable=False)
        result = svc.generate(definition.id, project_root=_PROJECT_ROOT)
        yield definition.id, result


def test_scaffold_new_feature_cria_estrutura_completa(generated_new_feature):
    feature_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon" / "features" / "feature_nova_feature"

    assert (feature_dir / "__init__.py").exists()
    assert (feature_dir / "feature.json").exists()
    assert (feature_dir / "feature.py").exists()
    assert (feature_dir / "model" / "feature_widget.py").exists()
    assert (feature_dir / "controller" / "__init__.py").exists()
    assert (feature_dir / "i18n" / "pt_BR.json").exists()
    assert (feature_dir / "docs" / "technical" / "01-visao-geral.md").exists()
    assert (feature_dir / "docs" / "manual" / "01-introducao.md").exists()


def test_scaffold_new_feature_manifesto_usa_nome_como_suffix_por_default(generated_new_feature):
    feature_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon" / "features" / "feature_nova_feature"
    manifest = json.loads((feature_dir / "feature.json").read_text(encoding="utf-8"))
    assert manifest["table_prefix_suffix"] == "nova_feature"
    assert manifest["label"] == "Nova Feature"


def test_scaffold_new_feature_atualiza_features_do_addon_pai(generated_new_feature):
    addon_json_path = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon" / "addon.json"
    manifest = json.loads(addon_json_path.read_text(encoding="utf-8"))
    names = [f["name"] for f in manifest["features"]]
    assert "feature_nova_feature" in names


def test_scaffold_new_feature_py_sem_metodos_manuais(generated_new_feature):
    feature_dir = _PROJECT_ROOT / "addons" / "addon_scaffoldedaddon" / "features" / "feature_nova_feature"
    content = (feature_dir / "feature.py").read_text(encoding="utf-8")
    assert "def register_models" not in content
    assert "def register_routes" not in content
    assert "def get_transactions" not in content


def test_geracao_new_feature_tabela_com_prefixo_tri_nivel(generated_new_feature):
    _, result = generated_new_feature
    assert result["scaffolded_new_module"] is True
    assert result["table_name"] == "tesseract_scaffoldedaddon_nova_feature_feature_widget"


def test_scaffold_new_feature_sem_addon_pai_falha(app):
    with app.app_context():
        definition = svc.create_draft(
            target_addon_name="addon_que_nao_existe", target_feature_name="orfa",
            model_name="Orfa", table_short_name="orfa", created_by_user_id=None,
            is_new_feature=True,
            manifest_draft={"label": "X", "description": "y"},
        )
        svc.add_field(definition, field_name="name", field_type=ModelFieldType.STRING, label_text="Nome")
        with pytest.raises(svc.ModelBuilderError, match="addon.json não existe"):
            svc.generate(definition.id, project_root=_PROJECT_ROOT)
