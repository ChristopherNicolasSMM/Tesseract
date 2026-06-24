"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_plant_vessels.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_plant_vessels_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_vessel_service import BrewPlantVesselService

brew_plant_vessels_bp = Blueprint(
    "brew_plant_vessels", __name__, url_prefix="/brewstation/brew-plant-vessels"
)
_service = BrewPlantVesselService()


@brew_plant_vessels_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_plant_vessels.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plant_vessels/manage.html", items=items, label="Vasilhame")


@brew_plant_vessels_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_plant_vessels.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_plant_vessels.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plant_vessels/detail.html", item=item, label="Vasilhame")


@brew_plant_vessels_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plant_vessels.manage"))


@brew_plant_vessels_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plant_vessels.manage"))


@brew_plant_vessels_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("brew_plant_vessels.manage"))


@brew_plant_vessels_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("brew_plant_vessels.manage"))


@brew_plant_vessels_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("brew_plant_vessels.manage"))
