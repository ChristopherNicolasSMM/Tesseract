"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_session_steps.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_session_steps_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_session_step_service import BrewSessionStepService

brew_session_steps_bp = Blueprint(
    "brew_session_steps", __name__, url_prefix="/brewstation/brew-session-steps"
)
_service = BrewSessionStepService()


@brew_session_steps_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_session_steps.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_session_steps/manage.html", items=items, label="Passo da Sessão")


@brew_session_steps_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_session_steps.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_session_steps.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_session_steps/detail.html", item=item, label="Passo da Sessão")


@brew_session_steps_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_session_steps.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_steps.manage"))


@brew_session_steps_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_session_steps.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_steps.manage"))


@brew_session_steps_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_session_steps.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("brew_session_steps.manage"))


@brew_session_steps_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_session_steps.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("brew_session_steps.manage"))


@brew_session_steps_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_session_steps.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("brew_session_steps.manage"))
