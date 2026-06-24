"""
addons/addon_brewstation/features/feature_yeast_bank/controller/yeast_strains.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via yeast_strains_hooks.py (nunca sobrescrito).
"""
import csv
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from annotations import get_choices_fields
from addons.addon_brewstation.features.feature_yeast_bank.services.yeast_strain_service import YeastStrainService
from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain

yeast_strains_bp = Blueprint(
    "yeast_strains", __name__, url_prefix="/brewstation/yeast-strains"
)
_service = YeastStrainService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in YeastStrain.__table__.columns if c.name not in _READONLY_FIELDS]

# Campo usado como "resumo" na coluna da lista — prefere um nome
# reconhecível em vez de simplesmente "a primeira coluna declarada"
# (que poderia ser algo pouco informativo como um campo de código).
_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)

# Campos booleanos — viram filtro <select> Todos/Sim/Não (smart-list-lite).
_BOOLEAN_FIELDS = [
    c.name for c in YeastStrain.__table__.columns
    if c.name in _EDITABLE_FIELDS and c.type.python_type is bool
]

# Campos com @choices no model — viram filtro <select> com valores
# distintos do banco (skill 00/04, anotação já existia desde a Fase 4
# mas nunca tinha sido conectada a nenhum filtro de verdade).
_CHOICES_FIELDS = [f["field"] for f in get_choices_fields(YeastStrain) if f["field"] in _EDITABLE_FIELDS]

_LIST_KEY = "yeast_strains"


def _get_column_prefs() -> list[str]:
    """
    Colunas visíveis na lista, por usuário — default é só o campo de
    resumo (mantém o comportamento anterior pra quem nunca configurou).
    """
    from model.core.user_list_preference import UserListPreference

    pref = UserListPreference.query.filter_by(user_id=current_user.id, list_key=_LIST_KEY).first()
    if pref and pref.visible_columns_json:
        # Filtra qualquer coluna que tenha deixado de existir (model mudou)
        return [c for c in pref.visible_columns_json if c in _EDITABLE_FIELDS] or [_SUMMARY_FIELD]
    return [_SUMMARY_FIELD]


def _apply_filters(query):
    """
    Compartilhado entre manage() e os exports — busca textual no campo
    de resumo + filtros tipados (boolean/choices) lidos da querystring.
    """
    search = (request.args.get("q") or "").strip()
    if search:
        search_field = getattr(YeastStrain, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    for field in _BOOLEAN_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value in ("true", "false"):
            query = query.filter(getattr(YeastStrain, field).is_(value == "true"))

    for field in _CHOICES_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value:
            query = query.filter(getattr(YeastStrain, field) == value)

    return query


def _choices_options() -> dict:
    """Valores distintos do banco para cada campo com @choices."""
    options = {}
    for field in _CHOICES_FIELDS:
        column = getattr(YeastStrain, field)
        rows = db.session.query(column).filter(column.isnot(None)).distinct().order_by(column).all()
        options[field] = [r[0] for r in rows]
    return options


@yeast_strains_bp.route("/", methods=["GET"])
@login_required
@permission_required("yeast_strains.list")
def manage():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = _apply_filters(YeastStrain.query.filter(YeastStrain.is_deleted.is_(False)))

    total = query.count()
    items = query.order_by(YeastStrain.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "yeast_strains/manage.html",
        items=items, label="Cepa de Levedura", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
        page=page, pages=pages, total=total, per_page=per_page, search=search,
        visible_columns=_get_column_prefs(),
        boolean_fields=_BOOLEAN_FIELDS, choices_fields=_CHOICES_FIELDS,
        choices_options=_choices_options(), request_args=request.args,
    )


@yeast_strains_bp.route("/column-prefs", methods=["POST"])
@login_required
@permission_required("yeast_strains.list")
def save_column_prefs():
    from model.core.user_list_preference import UserListPreference

    selected = [f for f in request.form.getlist("columns") if f in _EDITABLE_FIELDS]
    if not selected:
        selected = [_SUMMARY_FIELD]

    pref = UserListPreference.query.filter_by(user_id=current_user.id, list_key=_LIST_KEY).first()
    if not pref:
        pref = UserListPreference(user_id=current_user.id, list_key=_LIST_KEY)
        db.session.add(pref)
    pref.visible_columns_json = selected
    db.session.commit()

    flash("Colunas atualizadas.", "success")
    return redirect(url_for("yeast_strains.manage"))


@yeast_strains_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("yeast_strains.list")
def export_csv():
    query = _apply_filters(YeastStrain.query.filter(YeastStrain.is_deleted.is_(False)))
    items = query.order_by(YeastStrain.id.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id"] + _EDITABLE_FIELDS)
    for item in items:
        data = item.to_dict()
        writer.writerow([data.get("id")] + [data.get(f) for f in _EDITABLE_FIELDS])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={_LIST_KEY}.csv"},
    )


@yeast_strains_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("yeast_strains.list")
def export_xlsx():
    from openpyxl import Workbook

    query = _apply_filters(YeastStrain.query.filter(YeastStrain.is_deleted.is_(False)))
    items = query.order_by(YeastStrain.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Cepa de Levedura"[:31]  # limite do Excel pro nome da aba
    ws.append(["id"] + _EDITABLE_FIELDS)
    for item in items:
        data = item.to_dict()
        ws.append([data.get("id")] + [str(data.get(f)) if data.get(f) is not None else "" for f in _EDITABLE_FIELDS])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={_LIST_KEY}.xlsx"},
    )


@yeast_strains_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("yeast_strains.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("yeast_strains.manage"))
    return render_template(
        "yeast_strains/detail.html",
        item=item, label="Cepa de Levedura", fields=_EDITABLE_FIELDS,
    )


@yeast_strains_bp.route("/", methods=["POST"])
@login_required
@permission_required("yeast_strains.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("yeast_strains.manage"))


@yeast_strains_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("yeast_strains.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("yeast_strains.detail", id=id))


@yeast_strains_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("yeast_strains.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_strains.manage"))


@yeast_strains_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("yeast_strains.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_strains.manage"))


@yeast_strains_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("yeast_strains.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("yeast_strains.manage"))
