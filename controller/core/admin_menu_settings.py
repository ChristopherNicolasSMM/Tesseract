"""
controller/core/admin_menu_settings.py

Tela de edição do padrão GLOBAL de ordem/colapso de menu (skill 07 +
árvore skill 10). Preferência individual do usuário não passa por
aqui — vive em /perfil/menu-preferencias (controller/core/profile.py).
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from services.core import menu_preference_service as svc

admin_menu_settings_bp = Blueprint("admin_menu_settings", __name__, url_prefix="/admin/menu-settings")


@admin_menu_settings_bp.route("/", methods=["GET"])
@login_required
@permission_required("system_config.menu_settings")
def manage():
    return render_template(
        "core/admin/menu_settings.html",
        tree=svc.list_full_transaction_tree(),
        order_overrides=svc.get_global_order_overrides(),
        collapsed_nodes=set(svc.get_global_collapsed_nodes()),
        default_sidebar_collapsed=svc.get_global_default_sidebar_collapsed(),
    )


@admin_menu_settings_bp.route("/", methods=["POST"])
@login_required
@permission_required("system_config.menu_settings")
def save():
    try:
        order_overrides = json.loads(request.form.get("order_overrides_json") or "{}")
        collapsed_nodes = json.loads(request.form.get("collapsed_nodes_json") or "[]")
    except json.JSONDecodeError:
        flash("Dados de ordenação inválidos — tente novamente.", "error")
        return redirect(url_for("admin_menu_settings.manage"))

    default_sidebar_collapsed = bool(request.form.get("default_sidebar_collapsed"))

    svc.set_global_defaults(
        order_overrides=order_overrides,
        collapsed_nodes=collapsed_nodes,
        default_sidebar_collapsed=default_sidebar_collapsed,
    )
    flash("Padrão global de menu atualizado.", "success")
    return redirect(url_for("admin_menu_settings.manage"))
