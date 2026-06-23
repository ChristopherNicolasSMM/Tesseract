"""
api/routes/core/auth.py

Login/logout via sessão (Flask-Login). API pura nesta fase — sem
nenhuma tela HTML ainda.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, login_user, logout_user, current_user

from model.core.user import User

auth_api_bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@auth_api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify(success=False, error="Usuário ou senha inválidos."), 401
    if not user.is_active:
        return jsonify(success=False, error="Usuário desativado."), 403

    login_user(user)
    return jsonify(success=True, user=user.to_dict())


@auth_api_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(success=True)


@auth_api_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify(success=True, user=current_user.to_dict())
