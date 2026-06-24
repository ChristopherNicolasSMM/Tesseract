"""
addons/addon_brewstation/features/feature_mash_control/controller/dashboard_widgets.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via dashboard_widgets_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.dashboard_widget_service import DashboardWidgetService

dashboard_widgets_bp = Blueprint(
    "dashboard_widgets", __name__, url_prefix="/brewstation/dashboard-widgets"
)
_service = DashboardWidgetService()


@dashboard_widgets_bp.route("/", methods=["GET"])
@login_required
@permission_required("dashboard_widgets.list")
def manage():
    items = _service.list()
    return render_template("dashboard_widgets/manage.html", items=items, label="Widget de Dashboard")


@dashboard_widgets_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("dashboard_widgets.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("dashboard_widgets.manage"))
    return render_template("dashboard_widgets/detail.html", item=item, label="Widget de Dashboard")


@dashboard_widgets_bp.route("/", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_widgets.manage"))


@dashboard_widgets_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_widgets.manage"))


@dashboard_widgets_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("dashboard_widgets.manage"))


@dashboard_widgets_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("dashboard_widgets.manage"))


@dashboard_widgets_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("dashboard_widgets.manage"))
