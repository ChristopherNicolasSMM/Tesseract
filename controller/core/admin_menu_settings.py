"""
controller/core/admin_menu_settings.py

Tela de edição do padrão GLOBAL de ordem/colapso de menu (skill 07).
Preferência individual do usuário não passa por aqui — é sempre
sobrescrita a partir da própria sidebar (ver
api/routes/core/menu_preferences.py + core/base.html).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from model.core.transaction import Transaction
from services.core import menu_preference_service as svc

admin_menu_settings_bp = Blueprint("admin_menu_settings", __name__, url_prefix="/admin/menu-settings")


def _all_group_names() -> list[str]:
    groups = (
        Transaction.query.with_entities(Transaction.group)
        .filter(Transaction.is_active.is_(True), Transaction.group != "Core")
        .distinct()
        .all()
    )
    return sorted({g[0] for g in groups})


@admin_menu_settings_bp.route("/", methods=["GET"])
@login_required
@permission_required("system_config.menu_settings")
def manage():
    all_groups = _all_group_names()
    current_order = svc.get_global_group_order() or all_groups
    # Garante que grupos novos (sem posição salva ainda) apareçam no fim,
    # e que grupos removidos não quebrem a tela.
    ordered = [g for g in current_order if g in all_groups] + [g for g in all_groups if g not in current_order]

    return render_template(
        "core/admin/menu_settings.html",
        ordered_groups=ordered,
        default_collapsed=set(svc.get_global_default_collapsed_groups()),
        default_sidebar_collapsed=svc.get_global_default_sidebar_collapsed(),
    )


@admin_menu_settings_bp.route("/", methods=["POST"])
@login_required
@permission_required("system_config.menu_settings")
def save():
    group_order = request.form.getlist("group_order")
    default_collapsed = request.form.getlist("default_collapsed_groups")
    default_sidebar_collapsed = bool(request.form.get("default_sidebar_collapsed"))

    svc.set_global_defaults(
        group_order=group_order,
        default_collapsed_groups=default_collapsed,
        default_sidebar_collapsed=default_sidebar_collapsed,
    )
    flash("Padrão global de menu atualizado.", "success")
    return redirect(url_for("admin_menu_settings.manage"))
