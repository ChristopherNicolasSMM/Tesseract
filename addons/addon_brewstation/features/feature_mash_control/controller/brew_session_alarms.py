"""
addons/addon_brewstation/features/feature_mash_control/controller/brew_session_alarms.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via brew_session_alarms_hooks.py (nunca sobrescrito).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.services.brew_session_alarm_service import BrewSessionAlarmService
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm

brew_session_alarms_bp = Blueprint(
    "brew_session_alarms", __name__, url_prefix="/brewstation/brew-session-alarms"
)
_service = BrewSessionAlarmService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in BrewSessionAlarm.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)


@brew_session_alarms_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_session_alarms.list")
def manage():
    from flask import request

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = BrewSessionAlarm.query.filter(BrewSessionAlarm.is_deleted.is_(False))
    if search:
        search_field = getattr(BrewSessionAlarm, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    total = query.count()
    items = query.order_by(BrewSessionAlarm.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "brew_session_alarms/manage.html",
        items=items, label="Alarme da Sessão", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
        page=page, pages=pages, total=total, per_page=per_page, search=search,
    )


@brew_session_alarms_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("brew_session_alarms.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("brew_session_alarms.manage"))
    return render_template(
        "brew_session_alarms/detail.html",
        item=item, label="Alarme da Sessão", fields=_EDITABLE_FIELDS,
    )


@brew_session_alarms_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("brew_session_alarms.detail", id=id))


@brew_session_alarms_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_alarms.manage"))


@brew_session_alarms_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("brew_session_alarms.manage"))
