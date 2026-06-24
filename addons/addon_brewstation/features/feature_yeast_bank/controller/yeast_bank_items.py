"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_items.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_bank_items_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_item_service import YeastBankItemService

yeast_bank_items_bp = Blueprint(
    "yeast_bank_items", __name__, url_prefix="/brewstation/yeast-bank-items"
)
_service = YeastBankItemService()


@yeast_bank_items_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_bank_items.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_bank_items/manage.html", items=items, label="Item do Banco")


@yeast_bank_items_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_bank_items.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_bank_items.manage"))
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_bank_items/detail.html", item=item, label="Item do Banco")


@yeast_bank_items_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_items.manage"))


@yeast_bank_items_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_items.manage"))


@yeast_bank_items_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("yeast_bank_items.manage"))


@yeast_bank_items_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("yeast_bank_items.manage"))


@yeast_bank_items_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_bank_items.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("yeast_bank_items.manage"))
