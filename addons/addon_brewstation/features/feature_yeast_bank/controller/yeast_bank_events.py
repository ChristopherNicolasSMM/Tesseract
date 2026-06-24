"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_events.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_bank_events_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_event_service import YeastBankEventService

yeast_bank_events_bp = Blueprint(
    "yeast_bank_events", __name__, url_prefix="/brewstation/yeast-bank-events"
)
_service = YeastBankEventService()


@yeast_bank_events_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_bank_events.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_bank_events/manage.html", items=items, label="Evento do Banco")


@yeast_bank_events_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_bank_events.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_bank_events.manage"))
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_bank_events/detail.html", item=item, label="Evento do Banco")


@yeast_bank_events_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("yeast_bank_events.manage"))
