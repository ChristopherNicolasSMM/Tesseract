"""
addons/addon_brewstation/features/feature_device_manager/controller/device_actors.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via device_actors_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_device_manager.services.device_actor_service import DeviceActorService

device_actors_bp = Blueprint(
    "device_actors", __name__, url_prefix="/brewstation/device-actors"
)
_service = DeviceActorService()


@device_actors_bp.route("/", methods=["GET"])
@login_required
@permission_required("device_actors.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_device_manager/templates/device_actors/manage.html", items=items, label="Ator de Dispositivo")


@device_actors_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("device_actors.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("device_actors.manage"))
    return render_template("addons/addon_brewstation/features/feature_device_manager/templates/device_actors/detail.html", item=item, label="Ator de Dispositivo")


@device_actors_bp.route("/", methods=["POST"])
@login_required
@permission_required("device_actors.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_actors.manage"))


@device_actors_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("device_actors.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("device_actors.manage"))


@device_actors_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("device_actors.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("device_actors.manage"))


@device_actors_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("device_actors.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("device_actors.manage"))


@device_actors_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("device_actors.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("device_actors.manage"))
