"""
api/routes/core/theme.py

Preferência de tema (claro/escuro) por usuário — adaptado do
`update_theme` do PyTeca, com `theme` string ("light"/"dark") em vez
de boolean `modo_escuro`.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from core.db import db

theme_api_bp = Blueprint("theme_api", __name__, url_prefix="/api/auth")


@theme_api_bp.route("/update-theme", methods=["POST"])
@login_required
def update_theme():
    data = request.get_json(silent=True) or {}
    theme = data.get("theme")

    if theme not in ("light", "dark"):
        return jsonify(success=False, error="theme deve ser 'light' ou 'dark'."), 422

    current_user.theme = theme
    db.session.commit()
    return jsonify(success=True, theme=theme)
