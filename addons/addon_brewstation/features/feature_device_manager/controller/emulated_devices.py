"""
addons/addon_brewstation/features/feature_device_manager/controller/emulated_devices.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via emulated_devices_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.emulated_device_service import EmulatedDeviceService

emulated_devices_bp = Blueprint(
    "emulated_devices", __name__, url_prefix="/brewstation/emulated-devices"
)
_service = EmulatedDeviceService()


@emulated_devices_bp.route("/", methods=["GET"])
@login_required
@permission_required("emulated_devices.list")
def manage():
    items = _service.list()
    return render_template("emulated_devices/manage.html", items=items, label="Dispositivo Emulado")


@emulated_devices_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("emulated_devices.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("emulated_devices.manage"))
    return render_template("emulated_devices/detail.html", item=item, label="Dispositivo Emulado")


@emulated_devices_bp.route("/", methods=["POST"])
@login_required
@permission_required("emulated_devices.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("emulated_devices.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("emulated_devices.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("emulated_devices.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("emulated_devices.manage"))


@emulated_devices_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("emulated_devices.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("emulated_devices.manage"))
