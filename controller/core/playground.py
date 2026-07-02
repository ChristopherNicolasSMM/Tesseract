"""
controller/core/playground.py

Telas web do API/SQL Playground (skill 06, Patch C).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from model.core.playground_request import PlaygroundRequest, PlaygroundRequestKind
from services.core import playground_service as svc

playground_bp = Blueprint("playground", __name__, url_prefix="/admin/playground")


@playground_bp.route("/", methods=["GET"])
@login_required
@permission_required("playground_requests.execute")
def manage():
    http_history = (
        PlaygroundRequest.query.filter_by(kind=PlaygroundRequestKind.HTTP)
        .order_by(PlaygroundRequest.created_at.desc()).limit(20).all()
    )
    sql_history = (
        PlaygroundRequest.query.filter_by(kind=PlaygroundRequestKind.SQL)
        .order_by(PlaygroundRequest.created_at.desc()).limit(20).all()
    )
    return render_template(
        "core/admin/playground.html",
        http_history=http_history,
        sql_history=sql_history,
    )


@playground_bp.route("/http", methods=["POST"])
@login_required
@permission_required("playground_requests.execute")
def execute_http():
    headers_raw = (request.form.get("headers_json") or "").strip()
    body_raw = (request.form.get("body_json") or "").strip()

    import json
    try:
        headers = json.loads(headers_raw) if headers_raw else {}
        body = json.loads(body_raw) if body_raw else {}
    except json.JSONDecodeError as exc:
        flash(f"Headers/Body precisam ser JSON válido: {exc}", "error")
        return redirect(url_for("playground.manage"))

    record = svc.execute_http_request(
        name=(request.form.get("name") or "").strip() or None,
        method=request.form.get("http_method") or "GET",
        url=(request.form.get("url") or "").strip(),
        headers=headers,
        body=body,
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
