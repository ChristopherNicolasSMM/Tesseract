"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_plant_mappings.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_plant_mappings_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_mapping_service import BrewPlantMappingService

brew_plant_mappings_bp = Blueprint(
    "brew_plant_mappings", __name__, url_prefix="/brewstation/brew-plant-mappings"
)
_service = BrewPlantMappingService()


@brew_plant_mappings_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_plant_mappings.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plant_mappings/manage.html", items=items, label="Mapeamento de Equipamento")


@brew_plant_mappings_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_plant_mappings.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_plant_mappings.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_plant_mappings/detail.html", item=item, label="Mapeamento de Equipamento")


@brew_plant_mappings_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plant_mappings.manage"))


@brew_plant_mappings_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_plant_mappings.manage"))


@brew_plant_mappings_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("brew_plant_mappings.manage"))


@brew_plant_mappings_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("brew_plant_mappings.manage"))


@brew_plant_mappings_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("brew_plant_mappings.manage"))
