"""
addons/addon_brewstation/features/feature_device_manager/controller/device_metadatas.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via device_metadatas_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.device_metadata_service import DeviceMetadataService

device_metadatas_bp = Blueprint(
    "device_metadatas", __name__, url_prefix="/brewstation/device-metadatas"
)
_service = DeviceMetadataService()


@device_metadatas_bp.route("/", methods=["GET"])
@login_required
@permission_required("device_metadatas.list")
def manage():
    items = _service.list()
    return render_template("device_metadatas/manage.html", items=items, label="Dispositivo IoT")


@device_metadatas_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("device_metadatas.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("device_metadatas.manage"))
    return render_template("device_metadatas/detail.html", item=item, label="Dispositivo IoT")


@device_metadatas_bp.route("/", methods=["POST"])
@login_required
@permission_required("device_metadatas.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("device_metadatas.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("device_metadatas.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("device_metadatas.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("device_metadatas.manage"))


@device_metadatas_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("device_metadatas.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("device_metadatas.manage"))
