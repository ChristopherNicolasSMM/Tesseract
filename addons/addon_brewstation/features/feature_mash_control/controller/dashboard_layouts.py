"""
addons/addon_brewstation/features/feature_mash_control/controller/dashboard_layouts.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via dashboard_layouts_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.dashboard_layout_service import DashboardLayoutService

dashboard_layouts_bp = Blueprint(
    "dashboard_layouts", __name__, url_prefix="/brewstation/dashboard-layouts"
)
_service = DashboardLayoutService()


@dashboard_layouts_bp.route("/", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def manage():
    items = _service.list()
    return render_template("dashboard_layouts/manage.html", items=items, label="Layout de Dashboard")


@dashboard_layouts_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("dashboard_layouts.manage"))
    return render_template("dashboard_layouts/detail.html", item=item, label="Layout de Dashboard")


@dashboard_layouts_bp.route("/", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("dashboard_layouts.manage"))
