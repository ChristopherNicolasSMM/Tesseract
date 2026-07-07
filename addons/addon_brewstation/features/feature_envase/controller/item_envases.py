"""
addons/addon_brewstation/features/feature_envase/controller/item_envases.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via item_envases_hooks.py (nunca sobrescrito).
"""
import csv
import importlib
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from annotations import get_choices_fields, get_weak_refs
from addons.addon_brewstation.features.feature_envase.services.item_envase_service import ItemEnvaseService
from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase

item_envases_bp = Blueprint(
    "item_envases", __name__, url_prefix="/brewstation/item-envases"
)
_service = ItemEnvaseService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in ItemEnvase.__table__.columns if c.name not in _READONLY_FIELDS]

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
    c.name for c in ItemEnvase.__table__.columns
    if c.name in _EDITABLE_FIELDS and c.type.python_type is bool
]

# Campos com @choices no model — viram filtro <select> com valores
# distintos do banco (skill 00/04, anotação já existia desde a Fase 4
# mas nunca tinha sido conectada a nenhum filtro de verdade).
_CHOICES_FIELDS = [f["field"] for f in get_choices_fields(ItemEnvase) if f["field"] in _EDITABLE_FIELDS]

# Campos com @weak_ref no model (skill 11) — referência fraca (sem FK
# real, cross-Addon) resolvida em exibição via função apontada por
# "resolver". _WEAK_REFS guarda a declaração completa (field/resolver/
# options); _WEAK_REF_FIELDS é só a lista de nomes, usada pelo template
# pra decidir se substitui a célula pelo valor resolvido.
_WEAK_REFS = [wr for wr in get_weak_refs(ItemEnvase) if wr["field"] in _EDITABLE_FIELDS]
_WEAK_REF_FIELDS = [wr["field"] for wr in _WEAK_REFS]

_LIST_KEY = "item_envases"


def _resolve_weak_ref_display(item) -> dict:
    """
    Resolve os campos com @weak_ref (skill 11) para exibição, chamando
    a função apontada por "resolver" (caminho pontuado, resolvido via
    importlib). Nunca levanta erro pra fora — referência fraca não tem
    garantia de integridade (ex.: registro apagado do outro lado), e a
    tela sempre pode cair pro valor cru sem quebrar.
    """
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


def _get_field_rules() -> dict:
    """
    Regras de validação ativas para esta entidade, por campo —
    {"name": [{"js_function": "required", "params": {...}}, ...]}.
    Motor real só pra grupo Validação (core/rules_catalog.py) — outros
    grupos ficam ignorados pelo rule_engine.js (sem erro, sem efeito).
    """
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
        search_field = getattr(ItemEnvase, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    for field in _BOOLEAN_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value in ("true", "false"):
            query = query.filter(getattr(ItemEnvase, field).is_(value == "true"))

    for field in _CHOICES_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value:
            query = query.filter(getattr(ItemEnvase, field) == value)

    return query


def _choices_options() -> dict:
    """Valores distintos do banco para cada campo com @choices."""
    options = {}
    for field in _CHOICES_FIELDS:
        column = getattr(ItemEnvase, field)
        rows = db.session.query(column).filter(column.isnot(None)).distinct().order_by(column).all()
        options[field] = [r[0] for r in rows]
    return options


@item_envases_bp.route("/", methods=["GET"])
@login_required
@permission_required("item_envases.list")
def manage():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = _apply_filters(ItemEnvase.query.filter(ItemEnvase.is_deleted.is_(False)))

    total = query.count()
    items = query.order_by(ItemEnvase.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "item_envases/manage.html",
        items=items, label="Item de Envase", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
        page=page, pages=pages, total=total, per_page=per_page, search=search,
        visible_columns=_get_column_prefs(),
        boolean_fields=_BOOLEAN_FIELDS, choices_fields=_CHOICES_FIELDS,
        choices_options=_choices_options(), request_args=request.args,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display={item.id: _resolve_weak_ref_display(item) for item in items},
    )


@item_envases_bp.route("/column-prefs", methods=["POST"])
@login_required
@permission_required("item_envases.list")
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
    return redirect(url_for("item_envases.manage"))


@item_envases_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("item_envases.list")
def export_csv():
    query = _apply_filters(ItemEnvase.query.filter(ItemEnvase.is_deleted.is_(False)))
    items = query.order_by(ItemEnvase.id.desc()).all()

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


@item_envases_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("item_envases.list")
def export_xlsx():
    from openpyxl import Workbook

    query = _apply_filters(ItemEnvase.query.filter(ItemEnvase.is_deleted.is_(False)))
    items = query.order_by(ItemEnvase.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Item de Envase"[:31]  # limite do Excel pro nome da aba
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


@item_envases_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("item_envases.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("item_envases.manage"))
    return render_template(
        "item_envases/detail.html",
        item=item, label="Item de Envase", fields=_EDITABLE_FIELDS,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display=_resolve_weak_ref_display(item),
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
    )


@item_envases_bp.route("/", methods=["POST"])
@login_required
@permission_required("item_envases.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("item_envases.manage"))


@item_envases_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("item_envases.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("item_envases.detail", id=id))


@item_envases_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("item_envases.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("item_envases.manage"))


@item_envases_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("item_envases.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("item_envases.manage"))


@item_envases_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("item_envases.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("item_envases.manage"))
