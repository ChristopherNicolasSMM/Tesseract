"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_starter_logs.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_starter_logs_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_starter_log_service import YeastStarterLogService

yeast_starter_logs_bp = Blueprint(
    "yeast_starter_logs", __name__, url_prefix="/brewstation/yeast-starter-logs"
)
_service = YeastStarterLogService()


@yeast_starter_logs_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_starter_logs.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_starter_logs/manage.html", items=items, label="Starter")


@yeast_starter_logs_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_starter_logs.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_starter_logs.manage"))
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_starter_logs/detail.html", item=item, label="Starter")


@yeast_starter_logs_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_starter_logs.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_starter_logs.manage"))


@yeast_starter_logs_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_starter_logs.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_starter_logs.manage"))


@yeast_starter_logs_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_starter_logs.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("yeast_starter_logs.manage"))


@yeast_starter_logs_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_starter_logs.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("yeast_starter_logs.manage"))


@yeast_starter_logs_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_starter_logs.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("yeast_starter_logs.manage"))
