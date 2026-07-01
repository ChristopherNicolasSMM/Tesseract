"""
api/routes/core/menu_preferences.py

Persistência do override individual de menu (skill 07) — sidebar
aberta/fechada, grupos colapsados, ordem de grupos. Sempre escopado ao
próprio current_user; não precisa de permissão além de estar logado
(skill 07 §4).
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from services.core import menu_preference_service as svc

menu_preferences_api_bp = Blueprint("menu_preferences_api", __name__, url_prefix="/api/menu-preference")


@menu_preferences_api_bp.route("", methods=["POST"])
@login_required
def save():
    data = request.get_json(silent=True) or {}
    svc.save_user_preference(
        current_user.id,
        group_order=data.get("group_order"),
        collapsed_groups=data.get("collapsed_groups"),
        sidebar_collapsed=data.get("sidebar_collapsed"),
    )
    return jsonify(success=True)
