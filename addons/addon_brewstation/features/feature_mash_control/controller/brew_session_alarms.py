"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_session_alarms.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_session_alarms_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_session_alarm_service import BrewSessionAlarmService

brew_session_alarms_bp = Blueprint(
    "brew_session_alarms", __name__, url_prefix="/brewstation/brew-session-alarms"
)
_service = BrewSessionAlarmService()


@brew_session_alarms_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_session_alarms.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_session_alarms/manage.html", items=items, label="Alarme da Sessão")


@brew_session_alarms_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_session_alarms.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_session_alarms.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/brew_session_alarms/detail.html", item=item, label="Alarme da Sessão")


@brew_session_alarms_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("brew_session_alarms.manage"))
