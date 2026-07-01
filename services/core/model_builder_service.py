"""
services/core/model_builder_service.py

Orquestra o Model Builder Visual (skill 06). Patch A: só cobre
target_scope "existing_addon"/"existing_feature" — "new_addon"/
"new_feature" (scaffold completo de pastas+manifesto) fica para o
Patch B (skill 06, seção 3.3).

Reaproveita o pipeline já existente do CrudGen (core/crudgen/generator.py)
para Service/Controller/Routes/Templates — este módulo só cuida da
parte que o CLI não cobria: escrever o model.py a partir do rascunho
salvo no banco, e disparar a migration.
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

_NOT_IMPLEMENTED_SCOPES = (ModelDefinitionScope.NEW_ADDON, ModelDefinitionScope.NEW_FEATURE)


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


# ── Rascunho (ModelDefinition + campos) ──────────────────────────────────────

def create_draft(*, target_addon_name: str, target_feature_name: Optional[str],
                  model_name: str, table_short_name: str, created_by_user_id: Optional[int]) -> ModelDefinition:
    target_scope = (
        ModelDefinitionScope.EXISTING_FEATURE if target_feature_name
        else ModelDefinitionScope.EXISTING_ADDON
    )
    definition = ModelDefinition(
        target_scope=target_scope,
        target_addon_name=target_addon_name,
        target_feature_name=target_feature_name or None,
        model_name=model_name,
        table_short_name=table_short_name,
        status=ModelDefinitionStatus.DRAFT,
        created_by_user_id=created_by_user_id,
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

    if definition.target_scope in _NOT_IMPLEMENTED_SCOPES:
        raise ModelBuilderError(
            f"target_scope='{definition.target_scope}' ainda não é suportado "
            f"nesta versão do Model Builder (skill 06, Patch B — scaffold de "
            f"Addon/Feature novo do zero). Use um Addon/Feature já existente."
        )

    if not definition.fields:
        raise ModelBuilderError("Adicione pelo menos um campo antes de gerar.")

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
    }
