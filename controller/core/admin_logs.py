"""
controller/core/admin_logs.py

Tela HTML de consulta/exclusão de logs (skill 08 §6) — permissão flat
"admin", igual às demais 8 telas admin do Core (Users, Roles,
Versioning, Field Rules, OData, Designer, Transactions, Tasks). A
divisão logs.view/logs.delete cogitada originalmente na skill 08 foi
descartada em favor de manter esse padrão único — decisão revisada
em conversa de arquitetura, 2026-07-01.

Filtro por data/hora + cor por nível (adenda desta rodada, ver
BACKLOG.md "Item (b)"): `desde`/`ate` vêm de inputs `datetime-local`
do HTML5 (`YYYY-MM-DDTHH:MM`, sem segundos) — convertidos aqui pra
`datetime` antes de chegar em `LogAdminService.read_content()`.
"""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from core.permissions import permission_required
from core.log_admin_service import LogAdminService

admin_logs_bp = Blueprint("admin_logs", __name__, url_prefix="/admin/logs")


def _parse_datetime_local(valor: str | None) -> datetime | None:
    """`datetime-local` do HTML5 manda 'YYYY-MM-DDTHH:MM' (sem segundos)."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


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
    desde_raw = request.args.get("desde", "")
    ate_raw = request.args.get("ate", "")
    desde = _parse_datetime_local(desde_raw)
    ate = _parse_datetime_local(ate_raw)

    result = LogAdminService.read_content(source_id, desde=desde, ate=ate)
    if result["error"]:
        flash(result["error"], "error")
        return redirect(url_for("admin_logs.manage"))
    return render_template(
        "core/admin/logs_detail.html",
        source_id=source_id,
        lines=result["lines"],
        records=result["records"],
        truncated=result["truncated"],
        desde=desde_raw,
        ate=ate_raw,
        filtro_ativo=bool(desde or ate),
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
