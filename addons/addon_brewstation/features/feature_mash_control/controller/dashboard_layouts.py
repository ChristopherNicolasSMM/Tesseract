"""
addons/addon_brewstation/features/feature_mash_control/controller/dashboard_layouts.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via dashboard_layouts_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.dashboard_layout_service import DashboardLayoutService
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout

dashboard_layouts_bp = Blueprint(
    "dashboard_layouts", __name__, url_prefix="/brewstation/dashboard-layouts"
)
_service = DashboardLayoutService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in DashboardLayout.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)


@dashboard_layouts_bp.route("/", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def manage():
    items = _service.list()
    return render_template(
        "dashboard_layouts/manage.html",
        items=items, label="Layout de Dashboard", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
    )


@dashboard_layouts_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("dashboard_layouts.manage"))
    return render_template(
        "dashboard_layouts/detail.html",
        item=item, label="Layout de Dashboard", fields=_EDITABLE_FIELDS,
    )


@dashboard_layouts_bp.route("/", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("dashboard_layouts.detail", id=id))


@dashboard_layouts_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_layouts.manage"))


@dashboard_layouts_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("dashboard_layouts.manage"))
