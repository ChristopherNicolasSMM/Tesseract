"""
addons/addon_brewstation/features/feature_mash_control/controller/recipe_steps.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via recipe_steps_hooks.py (nunca sobrescrito).
"""
import csv
import importlib
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from annotations import get_choices_fields, get_weak_refs, get_enum_fields, get_model_metadata
from addons.addon_brewstation.features.feature_mash_control.services.recipe_step_service import RecipeStepService
from addons.addon_brewstation.features.feature_mash_control.model.recipe_step import RecipeStep

recipe_steps_bp = Blueprint(
    "recipe_steps", __name__, url_prefix="/brewstation/recipe-steps"
)
_service = RecipeStepService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"}
_EDITABLE_FIELDS = [c.name for c in RecipeStep.__table__.columns if c.name not in _READONLY_FIELDS]

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
    c.name for c in RecipeStep.__table__.columns
    if c.name in _EDITABLE_FIELDS and c.type.python_type is bool
]

# Campos com @choices no model — viram filtro <select> com valores
# distintos do banco (skill 00/04, anotação já existia desde a Fase 4
# mas nunca tinha sido conectada a nenhum filtro de verdade).
_CHOICES_FIELDS = [f["field"] for f in get_choices_fields(RecipeStep) if f["field"] in _EDITABLE_FIELDS]

# Campos com @weak_ref no model (skill 11) — referência fraca (sem FK
# real, cross-Addon) resolvida em exibição via função apontada por
# "resolver". _WEAK_REFS guarda a declaração completa (field/resolver/
# options); _WEAK_REF_FIELDS é só a lista de nomes, usada pelo template
# pra decidir se substitui a célula pelo valor resolvido.
_WEAK_REFS = [wr for wr in get_weak_refs(RecipeStep) if wr["field"] in _EDITABLE_FIELDS]
_WEAK_REF_FIELDS = [wr["field"] for wr in _WEAK_REFS]

_ENUM_FIELDS = [ef for ef in get_enum_fields(RecipeStep) if ef["field"] in _EDITABLE_FIELDS]
_ENUM_FIELD_OPTIONS = {ef["field"]: ef["options"] for ef in _ENUM_FIELDS}

# Tradução de @required/@max_length/@min_length/@min_value em
# atributos HTML5 nativos + badge visual (skill 12 — decisão desta
# sessão de ligar essas anotações a algo real; eram só decorativas
# antes). Camada complementar ao rule_engine.js (skill 07b) — validação
# nativa do browser, roda antes de qualquer JS, sem servidor envolvido.
_FIELD_HTML_VALIDATIONS: dict = {}
for _field, _rules in get_model_metadata(RecipeStep).get("validations", {}).items():
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

_LIST_KEY = "recipe_steps"


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
        search_field = getattr(RecipeStep, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    for field in _BOOLEAN_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value in ("true", "false"):
            query = query.filter(getattr(RecipeStep, field).is_(value == "true"))

    for field in _CHOICES_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value:
            query = query.filter(getattr(RecipeStep, field) == value)

    for _ef in _ENUM_FIELDS:
        if _ef["field"] in _CHOICES_FIELDS:
            continue  # já filtrado acima — evita duplicar a mesma condição
        value = request.args.get(f"filter_{_ef['field']}")
        if value:
            query = query.filter(getattr(RecipeStep, _ef["field"]) == value)

    return query


def _choices_options() -> dict:
    """Valores distintos do banco para cada campo com @choices."""
    options = {}
    for field in _CHOICES_FIELDS:
        column = getattr(RecipeStep, field)
        rows = db.session.query(column).filter(column.isnot(None)).distinct().order_by(column).all()
        options[field] = [r[0] for r in rows]
    return options


@recipe_steps_bp.route("/", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def manage():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = _apply_filters(RecipeStep.query.filter(RecipeStep.is_deleted.is_(False)))

    total = query.count()
    items = query.order_by(RecipeStep.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "recipe_steps/manage.html",
        items=items, label="Etapa da Receita", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
        page=page, pages=pages, total=total, per_page=per_page, search=search,
        visible_columns=_get_column_prefs(),
        boolean_fields=_BOOLEAN_FIELDS, choices_fields=_CHOICES_FIELDS,
        choices_options=_choices_options(), request_args=request.args,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display={item.id: _resolve_weak_ref_display(item) for item in items},
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
        weak_ref_value_fields={wr["field"]: wr["value_field"] for wr in _WEAK_REFS if wr.get("value_field")},
        enum_field_options=_ENUM_FIELD_OPTIONS,
        field_html_validations=_FIELD_HTML_VALIDATIONS,
    )


@recipe_steps_bp.route("/column-prefs", methods=["POST"])
@login_required
@permission_required("recipe_steps.list")
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
    return redirect(url_for("recipe_steps.manage"))


@recipe_steps_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def export_csv():
    query = _apply_filters(RecipeStep.query.filter(RecipeStep.is_deleted.is_(False)))
    items = query.order_by(RecipeStep.id.desc()).all()

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


@recipe_steps_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def export_xlsx():
    from openpyxl import Workbook

    query = _apply_filters(RecipeStep.query.filter(RecipeStep.is_deleted.is_(False)))
    items = query.order_by(RecipeStep.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Etapa da Receita"[:31]  # limite do Excel pro nome da aba
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


@recipe_steps_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("recipe_steps.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("recipe_steps.manage"))
    return render_template(
        "recipe_steps/detail.html",
        item=item, label="Etapa da Receita", fields=_EDITABLE_FIELDS,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display=_resolve_weak_ref_display(item),
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
        weak_ref_value_fields={wr["field"]: wr["value_field"] for wr in _WEAK_REFS if wr.get("value_field")},
        enum_field_options=_ENUM_FIELD_OPTIONS,
        field_html_validations=_FIELD_HTML_VALIDATIONS,
    )


@recipe_steps_bp.route("/", methods=["POST"])
@login_required
@permission_required("recipe_steps.create")
def create():
    result = _service.create(request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Criado com sucesso.", "success")
    return redirect(url_for("recipe_steps.manage"))


@recipe_steps_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("recipe_steps.update")
def update(id: int):
    result = _service.update(id, request.form.to_dict())
    if not result.success:
        flash(result.error, "error")
    else:
        flash("Salvo com sucesso.", "success")
    return redirect(url_for("recipe_steps.detail", id=id))


@recipe_steps_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("recipe_steps.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("recipe_steps.manage"))


@recipe_steps_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("recipe_steps.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("recipe_steps.manage"))


@recipe_steps_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("recipe_steps.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("recipe_steps.manage"))
