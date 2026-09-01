"""
addons/addon_brewstation/features/feature_mash_control/controller/water_profiles.py

Rotas web (HTML) — gerado pelo CrudGen. NÃO editar diretamente.
Customizações via water_profiles_hooks.py (nunca sobrescrito).
"""
import csv
import importlib
import io
import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from annotations import get_choices_fields, get_weak_refs, get_enum_fields, get_model_metadata, get_field_labels, get_readonly_fields
from core.crudgen.field_types import html_types_for_model
from addons.addon_brewstation.features.feature_mash_control.services.water_profile_service import WaterProfileService
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile

logger = logging.getLogger(__name__)

# Hooks de controller — achado real (skill 21): controller.py.j2 nunca
# importava/chamava water_profiles_hooks.py de verdade, só tinha o
# docstring aspiracional acima. Mesmo padrão seguro já usado em
# service.py.j2 (try/except + _hook() com fallback no-op) — hook
# ausente/sem a função específica não quebra nada, comportamento
# padrão de sempre continua valendo.
try:
    from addons.addon_brewstation.features.feature_mash_control.controller import water_profiles_hooks as _hooks
except ImportError:
    _hooks = None


def _noop(*args, **kwargs):
    return None


def _hook(name):
    return getattr(_hooks, name, _noop) if _hooks else _noop


water_profiles_bp = Blueprint(
    "water_profiles", __name__, url_prefix="/brewstation/water-profiles"
)
_service = WaterProfileService()

# Campos editáveis via formulário — calculado por introspecção das
# colunas do model (genérico, não precisa saber o schema de antemão).
_READONLY_FIELDS = {"id", "created_at", "updated_at", "is_deleted", "deleted_at"} | get_readonly_fields(WaterProfile)
_EDITABLE_FIELDS = [c.name for c in WaterProfile.__table__.columns if c.name not in _READONLY_FIELDS]

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
    c.name for c in WaterProfile.__table__.columns
    if c.name in _EDITABLE_FIELDS and c.type.python_type is bool
]

# Campos com @choices no model — viram filtro <select> com valores
# distintos do banco (skill 00/04, anotação já existia desde a Fase 4
# mas nunca tinha sido conectada a nenhum filtro de verdade).
_CHOICES_FIELDS = [f["field"] for f in get_choices_fields(WaterProfile) if f["field"] in _EDITABLE_FIELDS]

# Campos com @weak_ref no model (skill 11) — referência fraca (sem FK
# real, cross-Addon) resolvida em exibição via função apontada por
# "resolver". _WEAK_REFS guarda a declaração completa (field/resolver/
# options); _WEAK_REF_FIELDS é só a lista de nomes, usada pelo template
# pra decidir se substitui a célula pelo valor resolvido.
_WEAK_REFS = [wr for wr in get_weak_refs(WaterProfile) if wr["field"] in _EDITABLE_FIELDS]
_WEAK_REF_FIELDS = [wr["field"] for wr in _WEAK_REFS]

# Campos com @enum_field no model — opção FIXA (estática, declarada no
# código), vira <select> no formulário de detalhe. Diferente de
# @choices (dinâmico, só filtro de lista — ver _CHOICES_FIELDS acima).
_ENUM_FIELDS = [ef for ef in get_enum_fields(WaterProfile) if ef["field"] in _EDITABLE_FIELDS]
_ENUM_FIELD_OPTIONS = {ef["field"]: ef["options"] for ef in _ENUM_FIELDS}

# Tradução de @required/@max_length/@min_length/@min_value em
# atributos HTML5 nativos + badge visual (skill 12 — decisão desta
# sessão de ligar essas anotações a algo real; eram só decorativas
# antes). Camada complementar ao rule_engine.js (skill 07b) — validação
# nativa do browser, roda antes de qualquer JS, sem servidor envolvido.
_FIELD_HTML_VALIDATIONS: dict = {}
for _field, _rules in get_model_metadata(WaterProfile).get("validations", {}).items():
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

# Tipo real da coluna SQLAlchemy -> html_type (skill 20 — date,
# datetime-local, time, number+step, checkbox, textarea). Mescla no
# MESMO dict acima (chave html_type/step nova), nunca substitui o que
# já foi calculado por @required/@max_length/etc. Precedência real
# fica no template: @enum_field e @weak_ref continuam decidindo o
# campo ANTES de html_type ser consultado (skill 20, seção J) — este
# dict só alimenta o fallback final.
for _field, _html_attrs in html_types_for_model(WaterProfile, _EDITABLE_FIELDS).items():
    _FIELD_HTML_VALIDATIONS.setdefault(_field, {}).update(_html_attrs)

# Rótulos de campo em PT-BR (skill 12, @field_labels) — sem a
# anotação no model, o template cai no fallback de sempre
# (field.replace('_', ' ').title()).
_FIELD_LABELS: dict = get_field_labels(WaterProfile)

_LIST_KEY = "water_profiles"

# Ações em massa (skill 25) — Apagar sempre disponível (is_deleted já
# é padrão de todo model CrudGen). Inativar só aparece se este model
# tem coluna `ativo` própria, OU se algum @weak_ref declara
# bulk_deactivate_service (delega pro model do outro lado da
# referência fraca — ex.: Malte/Lúpulo/Levedura delegam pro
# Material.ativo). Nunca os dois ao mesmo tempo — local tem
# precedência se por acaso um model tiver as duas coisas.
_HAS_ATIVO_FIELD = any(f in _EDITABLE_FIELDS for f in ("ativo", "is_active"))
_DEACTIVATE_DELEGATE = None
if not _HAS_ATIVO_FIELD:
    _DEACTIVATE_DELEGATE = next((wr for wr in _WEAK_REFS if wr.get("bulk_deactivate_service")), None)
_PODE_INATIVAR_EM_MASSA = _HAS_ATIVO_FIELD or _DEACTIVATE_DELEGATE is not None


def _inactivate_many_delegated(ids: list[int]) -> dict:
    """
    Resolve os ids selecionados (desta entidade) para os valores do
    campo de referência fraca (ex.: material_id), deduplica, e chama a
    função pública apontada por bulk_deactivate_service — nunca ORM
    direto de outro Addon (skill 02). Ids da própria entidade que não
    tiverem o campo preenchido são reportados como falha, não pulados
    silenciosamente.
    """
    module_path, func_name = _DEACTIVATE_DELEGATE["bulk_deactivate_service"].rsplit(".", 1)
    delegate_fn = getattr(importlib.import_module(module_path), func_name)
    field = _DEACTIVATE_DELEGATE["field"]

    resultados = []
    valores_por_id: dict[int, int] = {}
    for id in ids:
        obj = db.session.get(WaterProfile, id)
        valor = getattr(obj, field, None) if obj else None
        if not obj or valor is None:
            resultados.append({"id": id, "sucesso": False, "erro": "Registro não encontrado ou sem referência preenchida."})
            continue
        valores_por_id[id] = valor

    valores_unicos = sorted(set(valores_por_id.values()))
    if valores_unicos:
        try:
            delegate_fn(valores_unicos, {"ativo": False})
            for id in valores_por_id:
                resultados.append({"id": id, "sucesso": True, "erro": None})
        except Exception as e:  # noqa: BLE001
            for id in valores_por_id:
                resultados.append({"id": id, "sucesso": False, "erro": str(e)})
    return {"resultados": resultados}


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
        search_field = getattr(WaterProfile, _SUMMARY_FIELD, None)
        if search_field is not None:
            query = query.filter(search_field.ilike(f"%{search}%"))

    for field in _BOOLEAN_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value in ("true", "false"):
            query = query.filter(getattr(WaterProfile, field).is_(value == "true"))

    for field in _CHOICES_FIELDS:
        value = request.args.get(f"filter_{field}")
        if value:
            query = query.filter(getattr(WaterProfile, field) == value)

    for _ef in _ENUM_FIELDS:
        if _ef["field"] in _CHOICES_FIELDS:
            continue  # já filtrado acima — evita duplicar a mesma condição
        value = request.args.get(f"filter_{_ef['field']}")
        if value:
            query = query.filter(getattr(WaterProfile, _ef["field"]) == value)

    return query


def _choices_options() -> dict:
    """Valores distintos do banco para cada campo com @choices."""
    options = {}
    for field in _CHOICES_FIELDS:
        column = getattr(WaterProfile, field)
        rows = db.session.query(column).filter(column.isnot(None)).distinct().order_by(column).all()
        options[field] = [r[0] for r in rows]
    return options


def _manage_context(submitted_data: dict | None = None, form_error: str | None = None) -> dict:
    """
    Monta o context de manage.html. Compartilhado entre manage() (GET)
    e create() (POST, quando falha) — achado real (BACKLOG.md): antes
    disso, um erro de validação no create() fazia redirect() e
    descartava TUDO que o usuário tinha digitado, forçando digitar de
    novo do zero. Com submitted_data preenchido, o formulário de
    "Novo registro" reabre com os valores que a pessoa já tinha
    digitado, só o(s) campo(s) com problema precisam ser corrigidos.
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = (request.args.get("q") or "").strip()

    query = _apply_filters(WaterProfile.query.filter(WaterProfile.is_deleted.is_(False)))

    total = query.count()
    items = query.order_by(WaterProfile.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)

    return dict(
        items=items, label="Perfil de Água", fields=_EDITABLE_FIELDS, summary_field=_SUMMARY_FIELD,
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
        field_labels=_FIELD_LABELS,
        submitted_data=submitted_data,
        form_error=form_error,
        pode_inativar_em_massa=_PODE_INATIVAR_EM_MASSA,
    )


@water_profiles_bp.route("/", methods=["GET"])
@login_required
@permission_required("water_profiles.list")
def manage():
    return render_template("water_profiles/manage.html", **_manage_context())


@water_profiles_bp.route("/column-prefs", methods=["POST"])
@login_required
@permission_required("water_profiles.list")
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
    return redirect(url_for("water_profiles.manage"))


@water_profiles_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("water_profiles.list")
def export_csv():
    query = _apply_filters(WaterProfile.query.filter(WaterProfile.is_deleted.is_(False)))
    items = query.order_by(WaterProfile.id.desc()).all()

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


@water_profiles_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("water_profiles.list")
def export_xlsx():
    from openpyxl import Workbook

    query = _apply_filters(WaterProfile.query.filter(WaterProfile.is_deleted.is_(False)))
    items = query.order_by(WaterProfile.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Perfil de Água"[:31]  # limite do Excel pro nome da aba
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


def _detail_context(item, submitted_data: dict | None = None, form_error: str | None = None) -> dict:
    """Compartilhado entre detail() (GET) e update() (POST, quando
    falha) — mesmo raciocínio do _manage_context() acima."""
    return dict(
        item=item, label="Perfil de Água", fields=_EDITABLE_FIELDS,
        field_rules=_get_field_rules(),
        weak_ref_fields=_WEAK_REF_FIELDS,
        weak_ref_display=_resolve_weak_ref_display(item),
        weak_ref_options={wr["field"]: wr["options"] for wr in _WEAK_REFS if wr["options"]},
        weak_ref_value_fields={wr["field"]: wr["value_field"] for wr in _WEAK_REFS if wr.get("value_field")},
        enum_field_options=_ENUM_FIELD_OPTIONS,
        field_html_validations=_FIELD_HTML_VALIDATIONS,
        field_labels=_FIELD_LABELS,
        submitted_data=submitted_data,
        form_error=form_error,
    )


@water_profiles_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("water_profiles.detail")
def detail(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("water_profiles.manage"))
    return render_template("water_profiles/detail.html", **_detail_context(item))


def _normalize_checkbox_fields(submitted: dict) -> dict:
    """
    HTML nunca manda o campo no POST quando um checkbox está
    desmarcado — sem isso, desmarcar um campo boolean que já estava
    `True` não teria efeito nenhum (o campo simplesmente não aparece
    em `request.form`, `_apply_fields` nunca o toca, o valor antigo
    persiste). Achado real (skill 20, risco documentado antes de
    implementar): força "false" pra todo `_BOOLEAN_FIELDS` ausente do
    submit, sem mexer nos que já vieram marcados.
    """
    for field in _BOOLEAN_FIELDS:
        if field not in submitted:
            submitted[field] = "false"
    return submitted


@water_profiles_bp.route("/", methods=["POST"])
@login_required
@permission_required("water_profiles.create")
def create():
    submitted = _normalize_checkbox_fields(request.form.to_dict())
    # Hook opcional (skill 21) — permite uma entidade bloquear
    # criação direta por essa tela (ex.: um registro que só deve
    # nascer a partir de um Evento de Banco, achado real: a via
    # direta continuava aberta mesmo depois da decisão).
    # Hook ausente/retornando None = comportamento padrão, sem bloqueio.
    _block_message = _hook("block_create")(submitted)
    if _block_message is not None:
        flash(_block_message, "error")
        return redirect(url_for("water_profiles.manage"))
    try:
        result = _service.create(submitted)
        success, error = result.success, result.error
    except Exception as e:  # noqa: BLE001
        # Achado real (BACKLOG.md): um hook que acessa relationship
        # (ex.: `if obj.strain:`) pode disparar autoflush ANTES do
        # try/except do service alcançar o commit — nesse caso o erro
        # (ex.: ValueError de coerção de tipo) escapa do
        # ServiceResult e vem parar aqui. Sem este catch, vira 500 e
        # perde o formulário do mesmo jeito que o redirect perdia.
        db.session.rollback()
        logger.warning("Erro inesperado ao criar WaterProfile: %s", e)
        success, error = False, str(e)
    if not success:
        # Achado real (BACKLOG.md): redirect() aqui descartava TUDO
        # que a pessoa tinha digitado em qualquer erro de validação —
        # não só erro de tipo (ex.: vírgula num Float), qualquer erro
        # de regra de negócio também. Re-renderiza com os valores
        # submetidos em vez de redirecionar; só o(s) campo(s) com
        # problema precisam ser corrigidos, o resto continua
        # preenchido.
        return render_template(
            "water_profiles/manage.html",
            **_manage_context(submitted_data=submitted, form_error=error),
        )
    flash("Criado com sucesso.", "success")
    # Hook opcional (skill 21) — permite uma entidade customizar o
    # destino do redirect depois de criar com sucesso (ex.: criar um
    # YeastBankEvent tipo "Starter" redireciona pra edição do Starter
    # recém-criado, não pra lista de eventos). Sem hook definido, cai
    # no redirect padrão de sempre.
    _redirect_override = _hook("post_create_redirect")(result.data)
    if _redirect_override is not None:
        return _redirect_override
    return redirect(url_for("water_profiles.manage"))


@water_profiles_bp.route("/<int:id>", methods=["POST"])
@login_required
@permission_required("water_profiles.update")
def update(id: int):
    item = _service.get_by_id(id)
    if not item:
        flash("Registro não encontrado.", "error")
        return redirect(url_for("water_profiles.manage"))

    submitted = _normalize_checkbox_fields(request.form.to_dict())
    try:
        result = _service.update(id, submitted)
        success, error = result.success, result.error
    except Exception as e:  # noqa: BLE001
        # Mesmo raciocínio do create() acima.
        db.session.rollback()
        logger.warning("Erro inesperado ao atualizar WaterProfile id=%s: %s", id, e)
        success, error = False, str(e)
    if not success:
        # Mesmo raciocínio do create() acima — re-renderiza com os
        # valores submetidos em vez de redirect() + perder tudo.
        return render_template(
            "water_profiles/detail.html",
            **_detail_context(item, submitted_data=submitted, form_error=error),
        )
    flash("Salvo com sucesso.", "success")
    return redirect(url_for("water_profiles.detail", id=id))


@water_profiles_bp.route("/<int:id>/trash", methods=["POST"])
@login_required
@permission_required("water_profiles.trash")
def trash(id: int):
    result = _service.trash(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("water_profiles.manage"))


@water_profiles_bp.route("/<int:id>/restore", methods=["POST"])
@login_required
@permission_required("water_profiles.restore")
def restore(id: int):
    result = _service.restore(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("water_profiles.manage"))


@water_profiles_bp.route("/<int:id>/delete-permanent", methods=["POST"])
@login_required
@permission_required("water_profiles.delete_permanent")
def delete_permanent(id: int):
    result = _service.delete_permanent(id)
    if not result.success:
        flash(result.error, "error")
    return redirect(url_for("water_profiles.manage"))


# Ações em massa (skill 25) — JSON, chamadas via fetch pelo JS genérico
# (core/static/js/crudgen-bulk-actions.js), mesmo padrão de resposta
# já usado em materials_hooks.py (achado real, addon_estoque).
def _bulk_ids_from_request() -> list[int]:
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    return [int(i) for i in ids if str(i).strip().isdigit()]


@water_profiles_bp.route("/bulk-trash", methods=["POST"])
@login_required
@permission_required("water_profiles.trash")
def bulk_trash():
    from flask import jsonify

    ids = _bulk_ids_from_request()
    if not ids:
        return jsonify({"success": False, "error": "Selecione ao menos um registro."}), 400
    resultado = _service.trash_many(ids)
    falhas = [r for r in resultado["resultados"] if not r["sucesso"]]
    return jsonify({
        "success": not falhas,
        "resultados": resultado["resultados"],
        "error": f"{len(falhas)} de {len(ids)} registro(s) falharam — veja o detalhe por linha." if falhas else None,
    })


@water_profiles_bp.route("/bulk-inactivate", methods=["POST"])
@login_required
@permission_required("water_profiles.update")
def bulk_inactivate():
    from flask import jsonify

    if not _PODE_INATIVAR_EM_MASSA:
        return jsonify({"success": False, "error": "Esta entidade não suporta inativação em massa."}), 400
    ids = _bulk_ids_from_request()
    if not ids:
        return jsonify({"success": False, "error": "Selecione ao menos um registro."}), 400
    if _HAS_ATIVO_FIELD:
        resultado = _service.inactivate_many(ids)
    else:
        resultado = _inactivate_many_delegated(ids)
    falhas = [r for r in resultado["resultados"] if not r["sucesso"]]
    return jsonify({
        "success": not falhas,
        "resultados": resultado["resultados"],
        "error": f"{len(falhas)} de {len(ids)} registro(s) falharam — veja o detalhe por linha." if falhas else None,
    })
