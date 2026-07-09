"""
controller/core/playground.py

Telas web do API/SQL Playground (skill 06, Patch C + adenda
"Playground v2", §8).
"""
import json
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from model.core.playground_request import PlaygroundRequest, PlaygroundRequestKind, PlaygroundAuthType
from services.core import playground_service as svc
from services.core import model_builder_service as model_builder_svc

playground_bp = Blueprint("playground", __name__, url_prefix="/admin/playground")


def _project_root() -> Path:
    return Path(current_app.root_path).parent.resolve()


def _build_auth_config(auth_type: str) -> dict:
    """Monta auth_config a partir dos campos discretos do formulário —
    a UI nunca pede pro usuário digitar JSON de auth na mão (skill 06
    §8.1)."""
    if auth_type == PlaygroundAuthType.BEARER:
        return {"token": (request.form.get("auth_bearer_token") or "").strip()}
    if auth_type == PlaygroundAuthType.BASIC:
        return {
            "username": (request.form.get("auth_basic_username") or "").strip(),
            "password": request.form.get("auth_basic_password") or "",
        }
    if auth_type == PlaygroundAuthType.API_KEY:
        return {
            "header_name": (request.form.get("auth_apikey_header_name") or "").strip(),
            "value": request.form.get("auth_apikey_value") or "",
        }
    return {}


@playground_bp.route("/", methods=["GET"])
@login_required
@permission_required("playground_requests.execute")
def manage():
    folder_id = request.args.get("folder_id", type=int)
    show_archived = request.args.get("show_archived") == "1"

    http_query = PlaygroundRequest.query.filter_by(kind=PlaygroundRequestKind.HTTP)
    sql_query = PlaygroundRequest.query.filter_by(kind=PlaygroundRequestKind.SQL)
    if not show_archived:
        http_query = http_query.filter_by(is_archived=False)
        sql_query = sql_query.filter_by(is_archived=False)
    if folder_id:
        http_query = http_query.filter_by(folder_id=folder_id)
        sql_query = sql_query.filter_by(folder_id=folder_id)

    http_history = http_query.order_by(PlaygroundRequest.created_at.desc()).limit(20).all()
    sql_history = sql_query.order_by(PlaygroundRequest.created_at.desc()).limit(20).all()

    return render_template(
        "core/admin/playground.html",
        http_history=http_history,
        sql_history=sql_history,
        folders=svc.list_folder_tree(),
        current_folder_id=folder_id,
        show_archived=show_archived,
        auth_types=PlaygroundAuthType.ALL,
        existing_addons=model_builder_svc.list_existing_addons(_project_root()),
    )


@playground_bp.route("/http", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def execute_http():
    headers_raw = (request.form.get("headers_json") or "").strip()
    body_raw = (request.form.get("body_json") or "").strip()
    params_raw = (request.form.get("params_json") or "").strip()
    auth_type = request.form.get("auth_type") or PlaygroundAuthType.NONE
    folder_id = request.form.get("folder_id", type=int)

    try:
        headers = json.loads(headers_raw) if headers_raw else {}
        body = json.loads(body_raw) if body_raw else {}
        params = json.loads(params_raw) if params_raw else []
    except json.JSONDecodeError as exc:
        flash(f"Headers/Body/Params precisam ser JSON válido: {exc}", "error")
        return redirect(url_for("playground.manage"))

    record = svc.execute_http_request(
        name=(request.form.get("name") or "").strip() or None,
        method=request.form.get("http_method") or "GET",
        url=(request.form.get("url") or "").strip(),
        headers=headers,
        body=body,
        params=params,
        auth_type=auth_type,
        auth_config=_build_auth_config(auth_type),
        folder_id=folder_id,
        created_by_user_id=current_user.id if current_user.is_authenticated else None,
    )
    if record.last_error:
        flash(f"Requisição falhou: {record.last_error}", "error")
    else:
        flash(f"OK — status {record.last_status_code}.", "success")
    return redirect(url_for("playground.manage", _anchor=f"req-{record.id}"))


@playground_bp.route("/sql", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def execute_sql():
    sql_text = (request.form.get("sql_text") or "").strip()
    try:
        record = svc.execute_sql_select(
            name=(request.form.get("name") or "").strip() or None,
            sql_text=sql_text,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
        flash(f"OK — {record.last_response_json['row_count']} linha(s).", "success")
        anchor = f"req-{record.id}"
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
        anchor = None

    return redirect(url_for("playground.manage", _anchor=anchor) if anchor else url_for("playground.manage"))


@playground_bp.route("/<int:request_id>/use-as-fields", methods=["POST"])
@login_required
@permission_required("model_definitions.create")
def use_as_fields(request_id: int):
    target_addon_name = (request.form.get("target_addon_name") or "").strip()
    target_feature_name = (request.form.get("target_feature_name") or "").strip() or None
    model_name = (request.form.get("model_name") or "").strip()
    table_short_name = (request.form.get("table_short_name") or "").strip()

    if not (target_addon_name and model_name and table_short_name):
        flash("Addon, nome do Model e nome curto da tabela são obrigatórios.", "error")
        return redirect(url_for("playground.manage"))

    try:
        definition = svc.create_model_definition_from_playground(
            request_id,
            target_addon_name=target_addon_name,
            target_feature_name=target_feature_name,
            model_name=model_name,
            table_short_name=table_short_name,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
        return redirect(url_for("playground.manage"))
    except Exception as exc:  # noqa: BLE001 — validação de manifest_draft/FK precisa chegar ao usuário
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("playground.manage"))

    flash("Rascunho criado no Model Builder com os campos inferidos — revise antes de gerar.", "success")
    return redirect(url_for("model_builder.detail", definition_id=definition.id))


# ── Pastas (skill 06 §8.2) ───────────────────────────────────────────────

@playground_bp.route("/folders", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def create_folder():
    name = (request.form.get("name") or "").strip()
    parent_id = request.form.get("parent_id", type=int)
    try:
        svc.create_folder(
            name=name, parent_id=parent_id,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
        flash(f"Pasta '{name}' criada.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage"))


@playground_bp.route("/folders/<int:folder_id>/delete", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def delete_folder(folder_id: int):
    try:
        svc.delete_folder(folder_id)
        flash("Pasta removida.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage"))


@playground_bp.route("/<int:request_id>/move", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def move_request(request_id: int):
    folder_id = request.form.get("folder_id", type=int)
    try:
        svc.move_request_to_folder(request_id, folder_id)
        flash("Requisição movida.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage"))


# ── Arquivar / Apagar (skill 06 §8.3) ───────────────────────────────────────

@playground_bp.route("/<int:request_id>/archive", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def archive_request(request_id: int):
    try:
        svc.set_archived(request_id, True)
        flash("Requisição arquivada.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage"))


@playground_bp.route("/<int:request_id>/unarchive", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def unarchive_request(request_id: int):
    try:
        svc.set_archived(request_id, False)
        flash("Requisição desarquivada.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage", show_archived="1"))


@playground_bp.route("/<int:request_id>/delete", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def delete_request(request_id: int):
    try:
        svc.delete_request(request_id)
        flash("Requisição apagada.", "success")
    except svc.PlaygroundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("playground.manage"))
