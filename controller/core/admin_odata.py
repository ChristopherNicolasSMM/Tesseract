"""
controller/core/admin_odata.py

Gestão de conexões OData + navegador de dados read-only. Escopo da
Fase 8 (decisão registrada em BACKLOG.md): só conectar, descobrir
metadata, e navegar dados — geração de tela completa
(`screen_generator.py` do DEVStationFlask) fica para quando o
Designer (Fase 7c) existir, já que ele gera `Component`/`Page`, que
não existem no Tesseract ainda.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from core.odata.connection_manager import ODataConnectionManager
from model.core.odata_connection import ODataConnection

admin_odata_bp = Blueprint("admin_odata", __name__, url_prefix="/admin/odata")


@admin_odata_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    connections = ODataConnection.query.order_by(ODataConnection.name).all()
    return render_template("core/admin/odata_manage.html", connections=connections)


@admin_odata_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    name = (request.form.get("name") or "").strip()
    base_url = (request.form.get("base_url") or "").strip()
    auth_type = request.form.get("auth_type") or "none"
    auth_value = (request.form.get("auth_value") or "").strip() or None

    if not name or not base_url:
        flash("Nome e URL base são obrigatórios.", "error")
        return redirect(url_for("admin_odata.manage"))

    conn = ODataConnection(
        name=name, base_url=base_url, auth_type=auth_type, auth_value=auth_value,
        created_by_user_id=current_user.id,
    )
    db.session.add(conn)
    db.session.commit()
    flash(f"Conexão '{name}' criada.", "success")
    return redirect(url_for("admin_odata.manage"))


@admin_odata_bp.route("/<int:conn_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(conn_id: int):
    conn = ODataConnection.query.get(conn_id)
    if conn:
        db.session.delete(conn)
        db.session.commit()
        flash("Conexão removida.", "success")
    return redirect(url_for("admin_odata.manage"))


@admin_odata_bp.route("/<int:conn_id>/test", methods=["POST"])
@login_required
@permission_required("admin")
def test(conn_id: int):
    conn = ODataConnection.query.get(conn_id)
    if not conn:
        flash("Conexão não encontrada.", "error")
        return redirect(url_for("admin_odata.manage"))

    result = ODataConnectionManager(conn).test_connection()
    if result["ok"]:
        flash(result["message"], "success")
    else:
        flash(f"Falha ao conectar: {result['error']}", "error")
    return redirect(url_for("admin_odata.manage"))


@admin_odata_bp.route("/<int:conn_id>/entities", methods=["GET"])
@login_required
@permission_required("admin")
def entities(conn_id: int):
    conn = ODataConnection.query.get(conn_id)
    if not conn:
        flash("Conexão não encontrada.", "error")
        return redirect(url_for("admin_odata.manage"))

    try:
        entity_list = ODataConnectionManager(conn).list_entities()
        error = None
    except Exception as e:
        entity_list = []
        error = str(e)

    return render_template(
        "core/admin/odata_entities.html",
        conn=conn, entities=entity_list, error=error,
    )


@admin_odata_bp.route("/<int:conn_id>/browse/<entity_name>", methods=["GET"])
@login_required
@permission_required("admin")
def browse(conn_id: int, entity_name: str):
    """Navegador de dados read-only — sem geração de tela (Fase 7c)."""
    conn = ODataConnection.query.get(conn_id)
    if not conn:
        flash("Conexão não encontrada.", "error")
        return redirect(url_for("admin_odata.manage"))

    manager = ODataConnectionManager(conn)
    entity = manager.get_entity(entity_name)
    if not entity:
        flash(f"Entidade '{entity_name}' não encontrada nesta conexão.", "error")
        return redirect(url_for("admin_odata.entities", conn_id=conn_id))

    page = request.args.get("page", 1, type=int)
    per_page = 20
    search = (request.args.get("q") or "").strip()

    params = {"$top": per_page, "$skip": (page - 1) * per_page, "$count": "true"}
    if search:
        text_fields = [f["name"] for f in entity.get("fields", []) if f.get("type") == "TEXT"]
        if text_fields:
            filters = " or ".join(f"contains({f},'{search}')" for f in text_fields[:5])
            params["$filter"] = filters

    error = None
    rows = []
    total = 0
    try:
        result = manager.query(entity_name, params)
        rows = result.get("value", result if isinstance(result, list) else [])
        total = result.get("@odata.count", len(rows)) if isinstance(result, dict) else len(rows)
    except Exception as e:
        error = str(e)

    field_names = [f["name"] for f in entity.get("fields", [])] or (list(rows[0].keys()) if rows else [])
    pages = max(1, (total + per_page - 1) // per_page) if total else 1

    return render_template(
        "core/admin/odata_browse.html",
        conn=conn, entity=entity, rows=rows, field_names=field_names,
        error=error, page=page, pages=pages, total=total, search=search,
    )
