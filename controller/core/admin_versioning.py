"""
controller/core/admin_versioning.py

Telas HTML de histórico de versionamento (CodeSnapshot) — só Admin,
já que isso expõe caminho de arquivo e conteúdo de código do servidor.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from core.permissions import permission_required
from core.snapshot_service import SnapshotService

admin_versioning_bp = Blueprint("admin_versioning", __name__, url_prefix="/admin/versioning")


@admin_versioning_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = request.args.get("q", "").strip() or None
    files = SnapshotService.list_files(search=search)
    return render_template("core/admin/versioning_manage.html", files=files, search=search or "")


@admin_versioning_bp.route("/history", methods=["GET"])
@login_required
@permission_required("admin")
def history():
    file_path = request.args.get("file_path", "")
    if not file_path:
        flash("Caminho de arquivo não informado.", "error")
        return redirect(url_for("admin_versioning.manage"))

    snapshots = SnapshotService.get_history(file_path)

    compare_a = request.args.get("a", type=int)
    compare_b = request.args.get("b", type=int)
    diff_result = None
    if compare_a and compare_b:
        diff_result = SnapshotService.diff(compare_a, compare_b)

    return render_template(
        "core/admin/versioning_history.html",
        file_path=file_path, snapshots=snapshots, diff_result=diff_result,
        compare_a=compare_a, compare_b=compare_b,
    )


@admin_versioning_bp.route("/restore/<int:snapshot_id>", methods=["POST"])
@login_required
@permission_required("admin")
def restore(snapshot_id: int):
    result = SnapshotService.restore(snapshot_id, created_by_user_id=current_user.id)
    file_path = request.form.get("file_path", "")
    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "error")
    return redirect(url_for("admin_versioning.history", file_path=file_path))
