"""
addons/addon_estoque/root/controller/movimentacaos.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via movimentacaos_hooks.py (nunca sobrescrito).

CORREÇÃO (achado do Christopher — combos de referência não
funcionavam, usuario_id nunca era preenchido): mesmo padrão de
materials.py/categorias.py — controller modernizado (weak_ref_fields/
enum_field_options/field_html_validations), create()/update() com
preservação de dado em erro. `usuario_id` deixou de ser campo editável
do formulário (nunca fazia sentido escolher "de quem" foi a
movimentação) — sempre auto-preenchido com o usuário logado.
`pedido_compra_item_id` também saiu do formulário manual (só é
preenchido pelo fluxo automático de Entrada de Mercadoria).
"""
import csv
import importlib
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from annotations import get_choices_fields, get_weak_refs, get_enum_fields, get_model_metadata, get_field_labels
from core.crudgen.field_types import html_types_for_model
from addons.addon_estoque.root.services.movimentacao_service import MovimentacaoService
from addons.addon_estoque.root.model.movimentacao import Movimentacao

movimentacaos_bp = Blueprint(
    "movimentacaos", __name__, url_prefix="/estoque/movimentacaos"
)
_service = MovimentacaoService()

# Campos editáveis via formulário — introspecção das colunas do model,
# EXCETO usuario_id/pedido_compra_item_id (nunca escolhidos à mão —
# ver docstring do módulo).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at", "usuario_id", "pedido_compra_item_id"}
_EDITABLE_FIELDS = [c.name for c in Movimentacao.__table__.columns if c.name not in _READONLY_FIELDS]

_SUMMARY_FIELD_PRIORITY = ("name", "label_text", "title", "username")
_SUMMARY_FIELD = next(
    (f for f in _SUMMARY_FIELD_PRIORITY if f in _EDITABLE_FIELDS),
    _EDITABLE_FIELDS[0] if _EDITABLE_FIELDS else "id",
)

_BOOLEAN_FIELDS = [
    c.name for c in Movimentacao.__table__.columns
    if c.name in _EDITABLE_FIELDS and c.type.python_type is bool
]

_CHOICES_FIELDS = [f["field"] for f in get_choices_fields(Movimentacao) if f["field"] in _EDITABLE_FIELDS]

_WEAK_REFS = [wr for wr in get_weak_refs(Movimentacao) if wr["field"] in _EDITABLE_FIELDS]
_WEAK_REF_FIELDS = [wr["field"] for wr in _WEAK_REFS]

_ENUM_FIELDS = [ef for ef in get_enum_fields(Movimentacao) if ef["field"] in _EDITABLE_FIELDS]
_ENUM_FIELD_OPTIONS = {ef["field"]: ef["options"] for ef in _ENUM_FIELDS}

_FIELD_HTML_VALIDATIONS: dict = {}
for _field, _rules in get_model_metadata(Movimentacao).get("validations", {}).items():
    if _field not in _EDITABLE_FIELDS:
        continue
    _attrs: dict = {}
    for _rule in _rules:
        if _rule["type"] == "required":
            _attrs["required"] = True
        elif _rule["type"] == "max_length":
            _attrs["maxlength"] = _rule.get("max")
        elif _rule["type"] == "min_length":
            _attrs["minlength"] = _rule.get("min")
        elif _rule["type"] == "min_value":
            _attrs["min_value"] = _rule.get("min")
    if _attrs:
        _FIELD_HTML_VALIDATIONS[_field] = _attrs
for _field, _html_attrs in html_types_for_model(Movimentacao, _EDITABLE_FIELDS).items():
    _FIELD_HTML_VALIDATIONS.setdefault(_field, {}).update(_html_attrs)

_FIELD_LABELS: dict = get_field_labels(Movimentacao)

_LIST_KEY = "movimentacaos"


def _resolve_weak_ref_display(item) -> dict:
    result: dict = {}
    for wr in _WEAK_REFS:
        value = getattr(item, wr["field"], None)
        if value is None:
            continue
        try:
            module_path, func_name = wr["resolver"].rsplit(".", 1)
            resolver_fn = getattr(importlib.import_module(module_path), func_name)
            resolved = resolver_fn(value)
        except Exception:  # noqa: BLE001
            continue
        if resolved and resolved.get("display"):
            result[wr["field"]] = resolved["display"]
    return result


def _resolve_usuario_nome(item) -> str | None:
    """usuario_id não passa por @weak_ref (não é campo editável) — só
    precisa resolver pra exibição, então uma consulta direta simples
    já basta, sem o mecanismo genérico de resolver/options."""
    if not item.usuario_id:
        return None
    from model.core.user import User
    usuario = db.session.get(User, item.usuario_id)
    return usuario.nome if usuario else None


def _get_field_rules() -> dict:
    from model.core.field_rule import FieldRule
    from core.rules_catalog import get_rule_def

    rules_by_field: dict = {}
    field_rules = (
        FieldRule.query
        .filter_by(entity_key=_LIST_KEY, is_active=True)
        .order_by(FieldRule.field_name, FieldRule.order)
        .all()
    )
    for fr in field_rules:
        rule_def = get_rule_def(fr.rule_id)
        if not rule_def:
            continue
        rules_by_field.setdefault(fr.field_name, []).append({
            "js_function": rule_def["js_function"],
            "params": fr.params_json or {},
        })
    return rules_by_field


def _get_column_prefs() -> list[str]:
    from model.core.user_list_preference import UserListPreference

    pref = UserListPreference.query.filter_by(user_id=current_user.id, list_key=_LIST_KEY).first()
    if pref and pref.visible_columns_json:
        return [c for c in pref.visible_columns_json if c in _EDITABLE_FIELDS] or [_SUMMARY_FIELD]
    return [_SUMMARY_FIELD]


def _apply_filters(query):
    search = (request.args.get("q") or "").strip()
    if search:
        search_field = getattr(Movimentacao, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    for field in _BOOLEAN_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value in ("true", "false"):
            query = query.filter(getattr(Movimentacao, field).is_(value == "true"))

    for field in _CHOICES_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value:
            query = query.filter(getattr(Movimentacao, field) == value)

    return query


def _choices_options() -> dict:
    options = {}
    for field in _CHOICES_FIELDS:
        column = getattr(Movimentacao, field)
        rows = db.session.query(column).filter(column.isnot(None)).distinct().order_by(column).all()
        options[field] = [r[0] for r in rows]
    return options


def _manage_context(submitted_data: dict | None = None, form_error: str | None = None) -> dict:
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = _apply_filters(Movimentacao.query.filter(Movimentacao.is_deleted.is_(False)))

    total = query.count()
    items = query.order_by(Movimentacao.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    weak_ref_display = {item.id: _resolve_weak_ref_display(item) for item in items}
    for item in items:
        nome_usuario = _resolve_usuario_nome(item)
        if nome_usuario:
            weak_ref_display.setdefault(item.id, {})["usuario_id"] = nome_usuario

    return dict(
        items=items, label="Movimentação de Estoque", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
        page=page, pages=pages, total=total, per_page=per_page, search=search,
        visible_columns=_get_column_prefs(),
        boolean_fields=_BOOLEAN_FIELDS, choices_fields=_CHOICES_FIELDS,
        choices_options=_choices_options(), request_args=request.args,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display=weak_ref_display,
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
        weak_ref_value_fields={wr["field"]: wr["value_field"] for wr in _WEAK_REFS if wr.get("value_field")},
        enum_field_options=_ENUM_FIELD_OPTIONS,
        field_html_validations=_FIELD_HTML_VALIDATIONS,
        field_labels=_FIELD_LABELS,
        submitted_data=submitted_data, form_error=form_error,
    )


def _detail_context(item, submitted_data: dict | None = None, form_error: str | None = None) -> dict:
    return dict(
        item=item, label="Movimentação de Estoque", fields=_EDITABLE_FIELDS,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display=_resolve_weak_ref_display(item),
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
        weak_ref_value_fields={wr["field"]: wr["value_field"] for wr in _WEAK_REFS if wr.get("value_field")},
        enum_field_options=_ENUM_FIELD_OPTIONS,
        field_html_validations=_FIELD_HTML_VALIDATIONS,
        field_labels=_FIELD_LABELS,
        usuario_nome=_resolve_usuario_nome(item),
        submitted_data=submitted_data, form_error=form_error,
    )


@movimentacaos_bp.route("/", methods=["GET"])
@login_required
@permission_required("movimentacaos.list")
def manage():
    return render_template("movimentacaos/manage.html", **_manage_context())


@movimentacaos_bp.route("/column-prefs", methods=["POST"])
@login_required
@permission_required("movimentacaos.list")
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
    return redirect(url_for("movimentacaos.manage"))


@movimentacaos_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("movimentacaos.list")
def export_csv():
    query = _apply_filters(Movimentacao.query.filter(Movimentacao.is_deleted.is_(False)))
    items = query.order_by(Movimentacao.id.desc()).all()

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


@movimentacaos_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("movimentacaos.list")
def export_xlsx():
    from openpyxl import Workbook

    query = _apply_filters(Movimentacao.query.filter(Movimentacao.is_deleted.is_(False)))
    items = query.order_by(Movimentacao.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Movimentação de Estoque"[:31]
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


@movimentacaos_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("movimentacaos.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("movimentacaos.manage"))
    return render_template("movimentacaos/detail.html", **_detail_context(item))


@movimentacaos_bp.route("/", methods=["POST"])
@login_required
@permission_required("movimentacaos.create")
def create():
    submitted = request.form.to_dict()
    submitted["usuario_id"] = current_user.id  # sempre o usuário logado, nunca escolhido no form
    try:
        result = _service.create(submitted)
        success, error = result.success, result.error
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        success, error = False, str(e)
    if not success:
        return render_template("movimentacaos/manage.html", **_manage_context(submitted_data=submitted, form_error=error))
    flash("Criado com sucesso.", "success")
    return redirect(url_for("movimentacaos.manage"))


@movimentacaos_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("movimentacaos.update")
def update(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("movimentacaos.manage"))

    submitted = request.form.to_dict()
    try:
        result = _service.update(id, submitted)
        success, error = result.success, result.error
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        success, error = False, str(e)
    if not success:
        return render_template("movimentacaos/detail.html", **_detail_context(item, submitted_data=submitted, form_error=error))
    flash("Salvo com sucesso.", "success")
    return redirect(url_for("movimentacaos.detail", id=id))


@movimentacaos_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("movimentacaos.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("movimentacaos.manage"))


@movimentacaos_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("movimentacaos.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("movimentacaos.manage"))


@movimentacaos_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("movimentacaos.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("movimentacaos.manage"))
