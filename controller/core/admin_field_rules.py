"""
controller/core/admin_field_rules.py

Tela de gestão de FieldRule — anexa regras do catálogo
(core/rules_catalog.py) a campos de qualquer entidade. Escopo desta
fase: só regras do grupo Validação têm efeito real (ver
static/js/rule_engine.js); as demais ficam catalogadas, sem motor.
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from core.rules_catalog import RULE_CATALOG, get_rule_def
from model.core.field_rule import FieldRule

admin_field_rules_bp = Blueprint("admin_field_rules", __name__, url_prefix="/admin/field-rules")

_EXPORT_HEADERS = ["entity_key", "field_name", "rule_id", "params_json", "is_active"]


def _filtered_query(search: str):
    query = FieldRule.query.order_by(FieldRule.entity_key, FieldRule.field_name)
    if search:
        like = f"%{search}%"
        query = query.filter(
            FieldRule.entity_key.ilike(like) | FieldRule.field_name.ilike(like) | FieldRule.rule_id.ilike(like)
        )
    return query


@admin_field_rules_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    rules, total, pages = paginate(_filtered_query(search), page)
    return render_template(
        "core/admin/field_rules_manage.html",
        rules=rules, catalog=RULE_CATALOG,
        search=search, total=total, page=page, pages=pages,
    )


@admin_field_rules_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    rows = [[r.entity_key, r.field_name, r.rule_id, r.params_json, r.is_active] for r in _filtered_query(search).all()]
    return export_csv_response(_EXPORT_HEADERS, rows, "regras_de_campo")


@admin_field_rules_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    rows = [[r.entity_key, r.field_name, r.rule_id, r.params_json, r.is_active] for r in _filtered_query(search).all()]
    return export_xlsx_response(_EXPORT_HEADERS, rows, "regras_de_campo", "Regras de Campo")


@admin_field_rules_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    entity_key = (request.form.get("entity_key") or "").strip()
    field_name = (request.form.get("field_name") or "").strip()
    rule_id = (request.form.get("rule_id") or "").strip()
    params_raw = (request.form.get("params_json") or "").strip() or "{}"

    if not entity_key or not field_name or not rule_id:
        flash("Entidade, campo e regra são obrigatórios.", "error")
        return redirect(url_for("admin_field_rules.manage"))

    if not get_rule_def(rule_id):
        flash(f"Regra '{rule_id}' não existe no catálogo.", "error")
        return redirect(url_for("admin_field_rules.manage"))

    try:
        params = json.loads(params_raw)
    except json.JSONDecodeError:
        flash("Parâmetros precisam ser um JSON válido (ex.: {\"min\": 3}).", "error")
        return redirect(url_for("admin_field_rules.manage"))

    rule = FieldRule(entity_key=entity_key, field_name=field_name, rule_id=rule_id, params_json=params)
    db.session.add(rule)
    db.session.commit()
    flash(f"Regra '{rule_id}' anexada a {entity_key}.{field_name}.", "success")
    return redirect(url_for("admin_field_rules.manage"))


@admin_field_rules_bp.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
@permission_required("admin")
def toggle(rule_id: int):
    rule = FieldRule.query.get(rule_id)
    if not rule:
        flash("Regra não encontrada.", "error")
        return redirect(url_for("admin_field_rules.manage"))
    rule.is_active = not rule.is_active
    db.session.commit()
    return redirect(url_for("admin_field_rules.manage"))


@admin_field_rules_bp.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(rule_id: int):
    rule = FieldRule.query.get(rule_id)
    if not rule:
        flash("Regra não encontrada.", "error")
        return redirect(url_for("admin_field_rules.manage"))
    db.session.delete(rule)
    db.session.commit()
    flash("Regra removida.", "success")
    return redirect(url_for("admin_field_rules.manage"))
