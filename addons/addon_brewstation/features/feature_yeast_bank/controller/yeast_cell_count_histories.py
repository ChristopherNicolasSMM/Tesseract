"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_cell_count_histories.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_cell_count_histories_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_cell_count_history_service import YeastCellCountHistoryService

yeast_cell_count_histories_bp = Blueprint(
    "yeast_cell_count_histories", __name__, url_prefix="/brewstation/yeast-cell-count-histories"
)
_service = YeastCellCountHistoryService()


@yeast_cell_count_histories_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_cell_count_histories.list")
def manage():
    items = _service.list()
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_cell_count_histories/manage.html", items=items, label="Histórico de Contagem")


@yeast_cell_count_histories_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_cell_count_histories.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_cell_count_histories.manage"))
    return render_template("addons/addon_brewstation/features/feature_yeast_bank/templates/yeast_cell_count_histories/detail.html", item=item, label="Histórico de Contagem")


@yeast_cell_count_histories_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_cell_count_histories.manage"))


@yeast_cell_count_histories_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_cell_count_histories.manage"))


@yeast_cell_count_histories_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.trash")
def trash(id: int):
    _service.trash(id)
    return redirect(url_for("yeast_cell_count_histories.manage"))


@yeast_cell_count_histories_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.restore")
def restore(id: int):
    _service.restore(id)
    return redirect(url_for("yeast_cell_count_histories.manage"))


@yeast_cell_count_histories_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_cell_count_histories.delete_permanent")
def delete_permanent(id: int):
    _service.delete_permanent(id)
    return redirect(url_for("yeast_cell_count_histories.manage"))
