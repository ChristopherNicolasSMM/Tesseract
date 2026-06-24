"""
addons/addon_brewstation/features/feature_device_manager/controller/device_functions.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via device_functions_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.device_function_service import DeviceFunctionService

device_functions_bp = Blueprint(
    "device_functions", __name__, url_prefix="/brewstation/device-functions"
)
_service = DeviceFunctionService()


@device_functions_bp.route("/", methods=["GET"])
@login_required
@permission_required("device_functions.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_device_manager/templates/device_functions/manage.html", items=items, label="Função de Dispositivo")


@device_functions_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("device_functions.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("device_functions.manage"))
    return render_template("addons/addon_brewstation/features/feature_device_manager/templates/device_functions/detail.html", item=item, label="Função de Dispositivo")


@device_functions_bp.route("/", methods=["POST"])
@login_required
@permission_required("device_functions.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_functions.manage"))


@device_functions_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("device_functions.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_functions.manage"))


@device_functions_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("device_functions.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("device_functions.manage"))


@device_functions_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("device_functions.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("device_functions.manage"))


@device_functions_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("device_functions.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("device_functions.manage"))
