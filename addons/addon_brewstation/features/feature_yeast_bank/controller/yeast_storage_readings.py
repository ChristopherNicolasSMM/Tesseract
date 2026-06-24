"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_storage_readings.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_storage_readings_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_storage_reading_service import YeastStorageReadingService

yeast_storage_readings_bp = Blueprint(
    "yeast_storage_readings", __name__, url_prefix="/brewstation/yeast-storage-readings"
)
_service = YeastStorageReadingService()


@yeast_storage_readings_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_storage_readings.list")
def manage():
    items = _service.list()
    return render_template("yeast_storage_readings/manage.html", items=items, label="Leitura de Armazenamento")


@yeast_storage_readings_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_storage_readings.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_storage_readings.manage"))
    return render_template("yeast_storage_readings/detail.html", item=item, label="Leitura de Armazenamento")


@yeast_storage_readings_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_storage_readings.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_storage_readings.manage"))


@yeast_storage_readings_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_storage_readings.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_storage_readings.manage"))


@yeast_storage_readings_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_storage_readings.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("yeast_storage_readings.manage"))


@yeast_storage_readings_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_storage_readings.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("yeast_storage_readings.manage"))


@yeast_storage_readings_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_storage_readings.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("yeast_storage_readings.manage"))
