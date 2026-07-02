"""
controller/core/model_builder.py

Telas web do Model Builder Visual (skill 06). Patch A cobre
"existing_addon"/"existing_feature"; Patch B (esta versão) adiciona
"new_addon"/"new_feature" — scaffold completo de pastas+manifesto+docs
antes de gerar o Model.
"""
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from model.core.model_definition import ModelDefinition
from model.core.model_field_definition import ModelFieldType
from services.core import model_builder_service as svc

model_builder_bp = Blueprint("model_builder", __name__, url_prefix="/admin/model-builder")


def _project_root() -> Path:
    return Path(current_app.root_path).parent.resolve()


@model_builder_bp.route("/", methods=["GET"])
@login_required
@permission_required("model_definitions.view")
def manage():
    definitions = ModelDefinition.query.order_by(ModelDefinition.created_at.desc()).all()
    return render_template("core/admin/model_builder_manage.html", definitions=definitions)


@model_builder_bp.route("/", methods=["POST"])
@login_required
@permission_required("model_definitions.create")
def create():
    target_addon_name = (request.form.get("target_addon_name") or "").strip()
    target_feature_name = (request.form.get("target_feature_name") or "").strip() or None
    model_name = (request.form.get("model_name") or "").strip()
    table_short_name = (request.form.get("table_short_name") or "").strip()

    is_new_addon = bool(request.form.get("is_new_addon"))
    is_new_feature = bool(request.form.get("is_new_feature"))

    if not (target_addon_name and model_name and table_short_name):
        flash("Addon, nome do Model e nome curto da tabela são obrigatórios.", "error")
        return redirect(url_for("model_builder.manage"))

    manifest_draft = None
    if is_new_addon or is_new_feature:
        manifest_draft = {
            "label": (request.form.get("manifest_label") or "").strip(),
            "description": (request.form.get("manifest_description") or "").strip(),
        }
        if is_new_addon:
            manifest_draft["author"] = (request.form.get("manifest_author") or "").strip()
        else:
            suffix = (request.form.get("manifest_table_prefix_suffix") or "").strip()
            if suffix:
                manifest_draft["table_prefix_suffix"] = suffix

    try:
        definition = svc.create_draft(
            target_addon_name=target_addon_name,
            target_feature_name=target_feature_name,
            model_name=model_name,
            table_short_name=table_short_name,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
            is_new_addon=is_new_addon,
            is_new_feature=is_new_feature,
            manifest_draft=manifest_draft,
        )
    except svc.ModelBuilderError as exc:
        flash(str(exc), "error")
        return redirect(url_for("model_builder.manage"))

    flash(f"Rascunho '{model_name}' criado — adicione os campos.", "success")
    return redirect(url_for("model_builder.detail", definition_id=definition.id))


@model_builder_bp.route("/<int:definition_id>", methods=["GET"])
@login_required
@permission_required("model_definitions.view")
def detail(definition_id: int):
    definition = ModelDefinition.query.get(definition_id)
    if not definition:
        flash("Rascunho não encontrado.", "error")
        return redirect(url_for("model_builder.manage"))
    return render_template(
        "core/admin/model_builder_detail.html",
        definition=definition,
        field_types=ModelFieldType.ALL,
        fk_candidates=svc.fk_candidates(definition),
    )


@model_builder_bp.route("/<int:definition_id>/fields", methods=["POST"])
@login_required
@permission_required("model_definitions.create")
def add_field(definition_id: int):
    definition = ModelDefinition.query.get(definition_id)
    if not definition:
        flash("Rascunho não encontrado.", "error")
        return redirect(url_for("model_builder.manage"))

    try:
        svc.add_field(
            definition,
            field_name=(request.form.get("field_name") or "").strip(),
            field_type=request.form.get("field_type"),
            label_text=(request.form.get("label_text") or "").strip(),
            nullable=bool(request.form.get("nullable")),
            unique=bool(request.form.get("unique")),
            is_required=bool(request.form.get("is_required")),
            default_value=(request.form.get("default_value") or "").strip() or None,
            max_length=request.form.get("max_length", type=int),
            fk_target_table=(request.form.get("fk_target_table") or "").strip() or None,
            is_listview_column=bool(request.form.get("is_listview_column")),
            is_form_field=bool(request.form.get("is_form_field")),
        )
        flash("Campo adicionado.", "success")
    except svc.ModelBuilderError as exc:
        flash(str(exc), "error")

    return redirect(url_for("model_builder.detail", definition_id=definition_id))


@model_builder_bp.route("/<int:definition_id>/fields/<int:field_id>/delete", methods=["POST"])
@login_required
@permission_required("model_definitions.create")
def delete_field(definition_id: int, field_id: int):
    svc.remove_field(field_id)
    flash("Campo removido.", "success")
    return redirect(url_for("model_builder.detail", definition_id=definition_id))


@model_builder_bp.route("/<int:definition_id>/generate", methods=["POST"])
@login_required
@permission_required("model_definitions.generate")
def generate(definition_id: int):
    overwrite = bool(request.form.get("overwrite"))
    try:
        result = svc.generate(definition_id, project_root=_project_root(), overwrite=overwrite)
        flash(
            ("Addon/Feature novo criado + " if result["scaffolded_new_module"] else "")
            + f"Gerado! Tabela: {result['table_name']}. "
            f"{len(result['written'])} arquivo(s) escrito(s). "
            + (
                f"Migration: {result['migration_message']}."
                if result["migration_message"]
                else "Migration pulada (ambiente de teste)."
            ),
            "success",
        )
    except svc.ModelBuilderError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    except Exception as exc:  # noqa: BLE001 — geração de código real, erro precisa chegar ao usuário
        db.session.rollback()
        current_app.logger.exception("Falha ao gerar model a partir do Model Builder")
        flash(f"Erro inesperado ao gerar: {exc}", "error")

    return redirect(url_for("model_builder.detail", definition_id=definition_id))
