"""
services/core/model_builder_service.py

Orquestra o Model Builder Visual (skill 06). Patch A cobriu
"existing_addon"/"existing_feature"; Patch B (esta versão) adiciona
"new_addon"/"new_feature" — scaffold completo de pastas (skill 01) +
manifesto (skill 03) + docs stub (skill 04) antes de gerar o Model.

Reaproveita o pipeline já existente do CrudGen (core/crudgen/generator.py)
para Service/Controller/Routes/Templates — este módulo cuida da parte
que o CLI não cobria: escrever o model.py (e, no Patch B, o próprio
addon.py/feature.py e manifesto) a partir do rascunho salvo no banco,
e disparar a migration.

Wiring pós-skill-09: addon.py/feature.py gerados aqui não escrevem
register_models()/register_routes()/get_transactions()/get_features()
nenhum — a auto-descoberta (skill 09 + adenda) resolve tudo sozinha no
próximo boot.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Optional

from flask import current_app
from jinja2 import Environment, FileSystemLoader

from core.db import db
from core.crudgen.generator import generate as run_crudgen_pipeline
from core.crudgen.manifest_utils import resolve_output_dir, ManifestError
from core.versioning import snapshot_if_needed
from model.core.model_definition import ModelDefinition, ModelDefinitionScope, ModelDefinitionStatus
from model.core.model_field_definition import ModelFieldDefinition, ModelFieldType

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "core" / "crudgen" / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ModelBuilderError(ValueError):
    pass


def _to_snake_case(name: str) -> str:
    """
    Mesma lógica de core/crudgen/generator._to_snake_case — duplicada
    de propósito (é um utilitário pequeno e estável; importar a versão
    "privada" de outro módulo criaria acoplamento desnecessário entre
    um service de UI e o gerador CLI).
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def _to_pascal_case(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_") if part)


# ── Rascunho (ModelDefinition + campos) ──────────────────────────────────────

def create_draft(*, target_addon_name: str, target_feature_name: Optional[str],
                  model_name: str, table_short_name: str, created_by_user_id: Optional[int],
                  is_new_addon: bool = False, is_new_feature: bool = False,
                  manifest_draft: Optional[dict] = None) -> ModelDefinition:
    if is_new_addon:
        target_scope = ModelDefinitionScope.NEW_ADDON
    elif is_new_feature:
        target_scope = ModelDefinitionScope.NEW_FEATURE
    elif target_feature_name:
        target_scope = ModelDefinitionScope.EXISTING_FEATURE
    else:
        target_scope = ModelDefinitionScope.EXISTING_ADDON

    if target_scope in (ModelDefinitionScope.NEW_ADDON, ModelDefinitionScope.NEW_FEATURE):
        _validate_manifest_draft(target_scope, target_addon_name, target_feature_name, manifest_draft or {})

    definition = ModelDefinition(
        target_scope=target_scope,
        target_addon_name=target_addon_name,
        target_feature_name=target_feature_name or None,
        model_name=model_name,
        table_short_name=table_short_name,
        status=ModelDefinitionStatus.DRAFT,
        created_by_user_id=created_by_user_id,
        manifest_draft_json=manifest_draft or None,
    )
    db.session.add(definition)
    db.session.commit()
    return definition


def add_field(model_definition: ModelDefinition, *, field_name: str, field_type: str,
              label_text: str, nullable: bool = True, unique: bool = False,
              is_required: bool = False, default_value: Optional[str] = None,
              max_length: Optional[int] = None, fk_target_table: Optional[str] = None,
              is_listview_column: bool = True, is_form_field: bool = True) -> ModelFieldDefinition:
    if field_type not in ModelFieldType.ALL:
        raise ModelBuilderError(f"Tipo de campo inválido: {field_type}")

    if field_type == ModelFieldType.FOREIGN_KEY:
        candidates = {c["table_name"] for c in fk_candidates(model_definition)}
        if fk_target_table not in candidates:
            raise ModelBuilderError(
                f"'{fk_target_table}' não é uma FK permitida para este Addon "
                f"(skill 02) — só tabelas do mesmo Addon ou tesseract_user."
            )

    order_index = len(model_definition.fields)
    field = ModelFieldDefinition(
        model_definition_id=model_definition.id,
        field_name=field_name,
        field_type=field_type,
        label_text=label_text,
        nullable=nullable,
        unique=unique,
        is_required=is_required,
        default_value=default_value,
        max_length=max_length,
        fk_target_table=fk_target_table if field_type == ModelFieldType.FOREIGN_KEY else None,
        is_listview_column=is_listview_column,
        is_form_field=is_form_field,
        order_index=order_index,
    )
    db.session.add(field)
    db.session.commit()
    return field


def remove_field(field_id: int) -> None:
    field = ModelFieldDefinition.query.get(field_id)
    if field:
        db.session.delete(field)
        db.session.commit()


def fk_candidates(model_definition: ModelDefinition) -> list[dict]:
    """
    Skill 02: FK só pode apontar para tabela do MESMO Addon (qualquer
    Feature dele) ou para tesseract_user (sempre permitido). Nunca
    lista tabela de outro Addon.
    """
    addon_prefix = f"tesseract_{model_definition.target_addon_name}_"
    result = [{"table_name": "tesseract_user", "label": "Usuário (Core)"}]
    for table_name in db.metadata.tables.keys():
        if table_name.startswith(addon_prefix):
            result.append({"table_name": table_name, "label": table_name})
    return result


# ── Patch B: validação + scaffold de Addon/Feature novo ─────────────────────

def _validate_manifest_draft(target_scope: str, target_addon_name: str,
                              target_feature_name: Optional[str], draft: dict) -> None:
    if not _NAME_RE.match(target_addon_name or ""):
        raise ModelBuilderError(
            f"'{target_addon_name}' inválido — nome de Addon deve ser snake_case (skill 00)."
        )
    if not (draft.get("label") or "").strip():
        raise ModelBuilderError("Label é obrigatório para criar Addon/Feature novo.")
    if not (draft.get("description") or "").strip():
        raise ModelBuilderError(
            "Description é obrigatório — vira o stub de docs/technical e "
            "docs/manual (skill 06 §3.3)."
        )

    if target_scope == ModelDefinitionScope.NEW_ADDON:
        if not (draft.get("author") or "").strip():
            raise ModelBuilderError("Author é obrigatório para criar Addon novo.")
        if len(target_addon_name) > 15:
            raise ModelBuilderError(
                f"'{target_addon_name}' tem {len(target_addon_name)} caracteres — "
                f"table_prefix de Addon recomendado no máximo 15 (skill 02)."
            )
    else:
        if not _NAME_RE.match(target_feature_name or ""):
            raise ModelBuilderError(
                f"'{target_feature_name}' inválido — nome de Feature deve ser "
                f"snake_case (skill 00)."
            )
        suffix = draft.get("table_prefix_suffix") or target_feature_name
        if len(suffix) > 12:
            raise ModelBuilderError(
                f"table_prefix_suffix '{suffix}' tem {len(suffix)} caracteres — "
                f"recomendado no máximo 12 (skill 02). Informe um "
                f"table_prefix_suffix mais curto no rascunho."
            )


def _write_docs_stub(module_dir: Path, *, label: str, description: str) -> None:
    """
    Stub automático (skill 06 §3.3, decisão confirmada) — nasce
    preenchido o suficiente para passar no checklist da skill 03 §6
    ("docs/technical/ e docs/manual/ presentes, com pelo menos 01-*.md
    preenchido"). Revisão/expansão do conteúdo continua manual depois.
    """
    tech_dir = module_dir / "docs" / "technical"
    manual_dir = module_dir / "docs" / "manual"
    tech_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)

    (tech_dir / "01-visao-geral.md").write_text(
        f"# 01 — Visão Geral: {label}\n\n"
        f"{description}\n\n"
        f"> Stub gerado automaticamente pelo Model Builder Visual (skill 06). "
        f"Completar com dependências (`requires`), o que este módulo expõe "
        f"(`provides`), e link para os demais documentos técnicos (skill 04).\n",
        encoding="utf-8",
    )
    (manual_dir / "01-introducao.md").write_text(
        f"# {label}\n\n"
        f"{description}\n\n"
        f"> Stub gerado automaticamente pelo Model Builder Visual (skill 06). "
        f"Completar explicando para que serve este módulo na prática, sem "
        f"mencionar termos de arquitetura (skill 04, regra de ouro).\n",
        encoding="utf-8",
    )


def _mkdir_package(path: Path) -> None:
    """Cria a pasta (se não existir) e o __init__.py dela (skill 01, adenda)."""
    path.mkdir(parents=True, exist_ok=True)
    init_file = path / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")


def _scaffold_new_addon(definition: ModelDefinition, project_root: Path) -> Path:
    draft = definition.manifest_draft_json or {}
    addon_name = definition.target_addon_name
    addon_dir = project_root / "addons" / f"addon_{addon_name}"
    if addon_dir.exists():
        raise ModelBuilderError(
            f"addons/addon_{addon_name} já existe em disco — use "
            f"target_scope=existing_addon em vez de new_addon."
        )

    class_name = f"Addon{_to_pascal_case(addon_name)}"
    manifest = {
        "name": addon_name,
        "label": draft["label"],
        "version": "1.0.0",
        "description": draft["description"],
        "author": draft["author"],
        "type": "addon",
        "table_prefix": addon_name,
        "tesseract_min_version": "1.0.0",
        "requires": [],
        "provides": [],
        "features": [],
        "env_keys": draft.get("env_keys") or [],
        "default_locale": "pt_BR",
        "available_locales": ["pt_BR"],
    }

    _mkdir_package(addon_dir)
    (addon_dir / "addon.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (addon_dir / "addon.py").write_text(
        f'"""\naddons/addon_{addon_name}/addon.py\n\n'
        f"Gerado pelo Model Builder Visual (skill 06, Patch B) a partir de "
        f"ModelDefinition #{definition.id}. Nenhum método sobrescrito de "
        f"propósito — register_models/register_routes/get_transactions/"
        f"get_features usam auto-descoberta (skill 09 + adenda); nada aqui "
        f"precisa ser editado à mão pra um Model/Feature novo aparecer.\n\"\"\"\n"
        f'__module__ = "{class_name}"\n\n'
        f"from core.addon_base import AddonBase\n\n\n"
        f"class {class_name}(AddonBase):\n"
        f"    pass\n",
        encoding="utf-8",
    )

    for sub in ("root", "root/model", "root/controller", "root/services", "root/api", "root/api/routes"):
        _mkdir_package(addon_dir / sub)

    _mkdir_package(addon_dir / "i18n")
    (addon_dir / "i18n" / "pt_BR.json").write_text("{}\n", encoding="utf-8")
    (addon_dir / "static").mkdir(parents=True, exist_ok=True)

    _write_docs_stub(addon_dir, label=draft["label"], description=draft["description"])

    return addon_dir


def _scaffold_new_feature(definition: ModelDefinition, project_root: Path) -> Path:
    draft = definition.manifest_draft_json or {}
    addon_name = definition.target_addon_name
    feature_name = definition.target_feature_name
    addon_dir = project_root / "addons" / f"addon_{addon_name}"
    addon_json_path = addon_dir / "addon.json"

    if not addon_json_path.exists():
        raise ModelBuilderError(
            f"addons/addon_{addon_name}/addon.json não existe — crie o Addon "
            f"primeiro (target_scope=new_addon) antes de adicionar uma Feature nele."
        )

    feature_dir = addon_dir / "features" / f"feature_{feature_name}"
    if feature_dir.exists():
        raise ModelBuilderError(
            f"features/feature_{feature_name} já existe em disco — use "
            f"target_scope=existing_feature em vez de new_feature."
        )

    suffix = draft.get("table_prefix_suffix") or feature_name
    class_name = f"Feature{_to_pascal_case(feature_name)}"
    manifest = {
        "name": f"feature_{feature_name}",
        "label": draft["label"],
        "version": "1.0.0",
        "description": draft["description"],
        "table_prefix_suffix": suffix,
        "enabled": True,
        "requires": [],
        "provides": [],
        "settings": {},
    }

    _mkdir_package(feature_dir)
    (feature_dir / "feature.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (feature_dir / "feature.py").write_text(
        f'"""\naddons/addon_{addon_name}/features/feature_{feature_name}/feature.py\n\n'
        f"Gerado pelo Model Builder Visual (skill 06, Patch B) a partir de "
        f"ModelDefinition #{definition.id}. Nenhum método sobrescrito de "
        f"propósito — register_models/register_routes/get_transactions usam "
        f"auto-descoberta (skill 09); nada aqui precisa ser editado à mão pra "
        f"um Model novo aparecer.\n\"\"\"\n"
        f'__module__ = "{class_name}"\n\n'
        f"from core.feature_base import FeatureBase\n\n\n"
        f"class {class_name}(FeatureBase):\n"
        f"    pass\n",
        encoding="utf-8",
    )

    for sub in ("model", "controller", "services", "api", "api/routes"):
        _mkdir_package(feature_dir / sub)

    _mkdir_package(feature_dir / "i18n")
    (feature_dir / "i18n" / "pt_BR.json").write_text("{}\n", encoding="utf-8")

    _write_docs_stub(feature_dir, label=draft["label"], description=draft["description"])

    # Achado registrado no BACKLOG (skill 09): addon.json["features"] não é
    # lido por nada operacionalmente hoje (get_features() usa auto-descoberta
    # de pasta) — escrito mesmo assim por consistência com a skill 03.
    addon_manifest = json.loads(addon_json_path.read_text(encoding="utf-8"))
    addon_manifest.setdefault("features", []).append({
        "name": f"feature_{feature_name}",
        "label": draft["label"],
        "table_prefix_suffix": suffix,
        "enabled_by_default": True,
        "requires": [],
    })
    addon_json_path.write_text(
        json.dumps(addon_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return feature_dir


# ── Geração ───────────────────────────────────────────────────────────────

def _field_template_context(fields: list[ModelFieldDefinition]) -> dict:
    rendered_fields = []
    for f in fields:
        default_repr = None
        if f.default_value is not None:
            if f.field_type in (ModelFieldType.INTEGER, ModelFieldType.FLOAT):
                default_repr = f.default_value
            elif f.field_type == ModelFieldType.BOOLEAN:
                default_repr = "True" if f.default_value.lower() in ("true", "1") else "False"
            else:
                default_repr = json.dumps(f.default_value, ensure_ascii=False)
        rendered_fields.append({
            "field_name": f.field_name,
            "field_type": f.field_type,
            "sqlalchemy_column": ModelFieldType.SQLALCHEMY_COLUMN[f.field_type],
            "nullable": f.nullable,
            "unique": f.unique,
            "max_length": f.max_length,
            "fk_target_table": f.fk_target_table,
            "default_value": f.default_value,
            "default_value_repr": default_repr,
        })
    return {
        "fields": rendered_fields,
        "required_fields": [f for f in fields if f.is_required],
        "max_length_fields": [f for f in fields if f.field_type == ModelFieldType.STRING and f.max_length],
    }


def _i18n_path(project_root: Path, addon: str, feature: Optional[str]) -> Path:
    """
    Skill 01: i18n/ vive na raiz do Addon (irmã de root/), ou na raiz
    da Feature quando target_scope é de Feature — nunca dentro de
    root/model/ ou features/[nome]/model/.
    """
    base = project_root / "addons" / f"addon_{addon}"
    if feature is None:
        return base / "i18n" / "pt_BR.json"
    return base / "features" / f"feature_{feature}" / "i18n" / "pt_BR.json"


def _merge_i18n_keys(i18n_path: Path, new_keys: dict[str, str]) -> None:
    existing = {}
    if i18n_path.exists():
        existing = json.loads(i18n_path.read_text(encoding="utf-8"))
    existing.update(new_keys)
    i18n_path.parent.mkdir(parents=True, exist_ok=True)
    i18n_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _run_migration_autogenerate(message: str) -> Optional[str]:
    """
    Sempre passa por Flask-Migrate (skill 06 §3.1 — nunca db.create_all()
    fora de teste). Gera o arquivo de migration e PARA — nunca aplica
    (`flask db upgrade` continua manual, mesmo fluxo já usado hoje).

    Pulado em TESTING pelo mesmo motivo que o cliente MQTT e o
    scheduler de tasks já pulam nesse modo (core/app_factory.py): o
    banco de teste nasce via db.create_all() direto, sem histórico de
    alembic_version, então autogenerate não tem base de comparação
    válida ali. Precisa de smoke-test manual em ambiente com migrations
    aplicadas de verdade.
    """
    if current_app.config.get("TESTING"):
        logger.info("TESTING=True: geração de migration pulada (mesmo padrão do MQTT/scheduler).")
        return None

    from flask_migrate import migrate as fm_autogenerate

    fm_autogenerate(directory="migrations", message=message)
    return message


def generate(model_definition_id: int, *, project_root: Path, overwrite: bool = False) -> dict:
    definition = ModelDefinition.query.get(model_definition_id)
    if not definition:
        raise ModelBuilderError("ModelDefinition não encontrado.")

    if not definition.fields:
        raise ModelBuilderError("Adicione pelo menos um campo antes de gerar.")

    scaffolded_new_module = False
    if definition.target_scope == ModelDefinitionScope.NEW_ADDON:
        _scaffold_new_addon(definition, project_root)
        scaffolded_new_module = True
    elif definition.target_scope == ModelDefinitionScope.NEW_FEATURE:
        _scaffold_new_feature(definition, project_root)
        scaffolded_new_module = True

    addon = definition.target_addon_name
    feature = definition.target_feature_name

    try:
        output_dir = resolve_output_dir(project_root, addon, feature)
    except ManifestError as exc:
        raise ModelBuilderError(str(exc)) from exc

    class_name = definition.model_name
    class_name_lower = _to_snake_case(class_name)

    context = {
        "class_name": class_name,
        "class_name_lower": class_name_lower,
        "table_short_name": definition.table_short_name,
        "label": definition.model_name,
        "plural": class_name_lower + "s",
        "output_module_path": str(output_dir.relative_to(project_root)),
        "model_definition_id": definition.id,
        **_field_template_context(definition.fields),
    }

    template = _jinja_env.get_template("model.py.j2")
    model_content = template.render(**context)

    model_dir = output_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"{class_name_lower}.py"

    if model_path.exists() and not overwrite:
        raise ModelBuilderError(
            f"{model_path} já existe. Marque 'sobrescrever' para regenerar "
            f"a partir do rascunho atual."
        )

    model_path.write_text(model_content, encoding="utf-8")
    snapshot_if_needed(str(model_path), model_content)

    # Import dinâmico do model recém-escrito, mesma técnica do CLI
    # (core/cli.py generate_cmd) — necessário para obter a classe já
    # registrada em db.metadata antes de chamar o pipeline do CrudGen.
    spec = importlib.util.spec_from_file_location(f"_model_builder_{class_name_lower}", model_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model_class = getattr(module, class_name)

    pipeline_result = run_crudgen_pipeline(
        model_class,
        project_root=project_root,
        addon=addon,
        feature=feature,
        overwrite=overwrite,
        triggered_by="ui:model_builder",
    )

    i18n_keys = {
        f"{addon}.{class_name_lower}.field_{f.field_name}": f.label_text
        for f in definition.fields
    }
    _merge_i18n_keys(_i18n_path(project_root, addon, feature), i18n_keys)

    migration_message = f"model_builder_add_{pipeline_result['table_name']}"
    migration_revision = _run_migration_autogenerate(migration_message)

    definition.status = ModelDefinitionStatus.GENERATED
    definition.error_message = None
    definition.generation_run_id = pipeline_result["generation_run_id"]
    definition.migration_revision = migration_revision
    from datetime import datetime, timezone
    definition.generated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "table_name": pipeline_result["table_name"],
        "written": [str(model_path)] + pipeline_result["written"],
        "permissions": pipeline_result["permissions"],
        "i18n_keys_written": list(i18n_keys.keys()),
        "migration_message": migration_revision,
        "scaffolded_new_module": scaffolded_new_module,
    }
