"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_plants.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_plants_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_service import BrewPlantService

brew_plants_bp = Blueprint(
    "brew_plants", __name__, url_prefix="/brewstation/brew-plants"
)
_service = BrewPlantService()


@brew_plants_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plants/manage.html", items=items, label="Planta de Brassagem")


@brew_plants_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_plants.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_plants.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plants/detail.html", item=item, label="Planta de Brassagem")


@brew_plants_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_plants.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plants.manage"))


@brew_plants_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_plants.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plants.manage"))


@brew_plants_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_plants.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("brew_plants.manage"))


@brew_plants_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_plants.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("brew_plants.manage"))


@brew_plants_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_plants.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("brew_plants.manage"))
