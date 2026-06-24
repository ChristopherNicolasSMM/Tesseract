"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_bank_events.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_bank_events_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_bank_event_service import YeastBankEventService
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent

yeast_bank_events_bp = Blueprint(
    "yeast_bank_events", __name__, url_prefix="/brewstation/yeast-bank-events"
)
_service = YeastBankEventService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in YeastBankEvent.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)


@yeast_bank_events_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_bank_events.list")
def manage():
    items = _service.list()
    return render_template(
        "yeast_bank_events/manage.html",
        items=items, label="Evento do Banco", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
    )


@yeast_bank_events_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_bank_events.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_bank_events.manage"))
    return render_template(
        "yeast_bank_events/detail.html",
        item=item, label="Evento do Banco", fields=_EDITABLE_FIELDS,
    )


@yeast_bank_events_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("yeast_bank_events.detail", id=id))


@yeast_bank_events_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_events.manage"))


@yeast_bank_events_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_bank_events.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_bank_events.manage"))
