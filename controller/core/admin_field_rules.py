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
from core.rules_catalog import RULE_CATALOG, get_rule_def
from model.core.field_rule import FieldRule

admin_field_rules_bp = Blueprint("admin_field_rules", __name__, url_prefix="/admin/field-rules")


@admin_field_rules_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    rules = FieldRule.query.order_by(FieldRule.entity_key, FieldRule.field_name).all()
    return render_template(
        "core/admin/field_rules_manage.html",
        rules=rules, catalog=RULE_CATALOG,
    )


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
