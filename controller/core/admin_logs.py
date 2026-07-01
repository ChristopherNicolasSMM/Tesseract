"""
controller/core/admin_logs.py

Tela HTML de consulta/exclusão de logs (skill 08 §6) — permissão flat
"admin", igual às demais 8 telas admin do Core (Users, Roles,
Versioning, Field Rules, OData, Designer, Transactions, Tasks). A
divisão logs.view/logs.delete cogitada originalmente na skill 08 foi
descartada em favor de manter esse padrão único — decisão revisada
em conversa de arquitetura, 2026-07-01.
"""
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from core.log_admin_service import LogAdminService

admin_logs_bp = Blueprint("admin_logs", __name__, url_prefix="/admin/logs")


@admin_logs_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    sources = LogAdminService.list_sources()
    return render_template("core/admin/logs_manage.html", sources=sources)


@admin_logs_bp.route("/view/<source_id>", methods=["GET"])
@login_required
@permission_required("admin")
def view(source_id: str):
    result = LogAdminService.read_content(source_id)
    if result["error"]:
        flash(result["error"], "error")
        return redirect(url_for("admin_logs.manage"))
    return render_template(
        "core/admin/logs_detail.html",
        source_id=source_id,
        lines=result["lines"],
        truncated=result["truncated"],
    )


@admin_logs_bp.route("/delete/<source_id>", methods=["POST"])
@login_required
@permission_required("admin")
def delete(source_id: str):
    result = LogAdminService.delete(source_id)
    if result["success"]:
        flash("Arquivo de log apagado — será recriado na próxima escrita.", "success")
    else:
        flash(result["error"], "error")
    return redirect(url_for("admin_logs.manage"))
