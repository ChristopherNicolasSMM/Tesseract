"""
addons/addon_brewstation/features/feature_mash_control/controller/automation_rules.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via automation_rules_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.automation_rule_service import AutomationRuleService

automation_rules_bp = Blueprint(
    "automation_rules", __name__, url_prefix="/brewstation/automation-rules"
)
_service = AutomationRuleService()


@automation_rules_bp.route("/", methods=["GET"])
@login_required
@permission_required("automation_rules.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/automation_rules/manage.html", items=items, label="Regra de Automação")


@automation_rules_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("automation_rules.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("automation_rules.manage"))
    return render_template("addons/addon_brewstation/features/feature_mash_control/templates/automation_rules/detail.html", item=item, label="Regra de Automação")


@automation_rules_bp.route("/", methods=["POST"])
@login_required
@permission_required("automation_rules.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("automation_rules.manage"))


@automation_rules_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("automation_rules.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("automation_rules.manage"))


@automation_rules_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("automation_rules.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("automation_rules.manage"))


@automation_rules_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("automation_rules.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("automation_rules.manage"))


@automation_rules_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("automation_rules.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("automation_rules.manage"))
