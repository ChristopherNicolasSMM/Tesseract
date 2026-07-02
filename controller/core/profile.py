"""
controller/core/profile.py

Tela "Meu Perfil" — o usuário edita os próprios dados e troca a
própria senha. Diferente de controller/core/admin_users.py: aqui não
exige permissão "admin", só estar logado (qualquer usuário edita o
próprio perfil).
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from core.db import db
from core.validators import validate_cpf, format_cpf
from services.core import menu_preference_service as menu_svc

profile_bp = Blueprint("profile", __name__, url_prefix="/perfil")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@profile_bp.route("/", methods=["GET"])
@login_required
def view_profile():
    return render_template("core/profile.html")


@profile_bp.route("/", methods=["POST"])
@login_required
def update_profile():
    user = current_user

    email = (request.form.get("email") or "").strip()
    nome = (request.form.get("nome") or "").strip()
    nome_completo = (request.form.get("nome_completo") or "").strip()
    celular = (request.form.get("celular") or "").strip()
    cpf = (request.form.get("cpf") or "").strip()

    if not email or not _EMAIL_RE.match(email):
        flash("E-mail em formato inválido.", "error")
        return redirect(url_for("profile.view_profile"))
    if not nome or not nome_completo or not celular:
        flash("Nickname, nome completo e celular são obrigatórios.", "error")
        return redirect(url_for("profile.view_profile"))

    if cpf:
        try:
            user.set_cpf(cpf)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("profile.view_profile"))

    user.email = email
    user.nome = nome
    user.nome_completo = nome_completo
    user.celular = celular

    for field in ("empresa", "cargo", "pais", "telefone", "endereco_rua",
                  "endereco_numero", "endereco_complemento", "endereco_bairro",
                  "endereco_cidade", "endereco_uf", "endereco_cep"):
        setattr(user, field, (request.form.get(field) or "").strip() or None)

    db.session.commit()
    flash("Perfil atualizado.", "success")
    return redirect(url_for("profile.view_profile"))


@profile_bp.route("/senha", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_user.check_password(current_password):
        flash("Senha atual incorreta.", "error")
        return redirect(url_for("profile.view_profile"))

    if len(new_password) < 6:
        flash("A nova senha deve ter pelo menos 6 caracteres.", "error")
        return redirect(url_for("profile.view_profile"))

    if new_password != confirm_password:
        flash("A confirmação não corresponde à nova senha.", "error")
        return redirect(url_for("profile.view_profile"))

    current_user.set_password(new_password)
    db.session.commit()
    flash("Senha alterada com sucesso.", "success")
    return redirect(url_for("profile.view_profile"))


@profile_bp.route("/menu-preferencias", methods=["GET"])
@login_required
def menu_preferences():
    """
    Override PESSOAL de ordem/colapso de menu (skill 07 + árvore
    skill 10) — não exige permissão além de login, escopo é sempre o
    próprio usuário. Mesmo molde da tela de admin
    (/admin/menu-settings), mas grava em tesseract_user_menu_preference
    em vez do padrão global.
    """
    state = menu_svc.resolve_menu_state(current_user.id)
    return render_template(
        "core/profile_menu_preferences.html",
        tree=menu_svc.list_full_transaction_tree(),
        collapsed_nodes=state["collapsed_nodes"],
        sidebar_collapsed=state["sidebar_collapsed"],
    )


@profile_bp.route("/menu-preferencias", methods=["POST"])
@login_required
def save_menu_preferences():
    import json

    try:
        order_overrides = json.loads(request.form.get("order_overrides_json") or "{}")
        collapsed_nodes = json.loads(request.form.get("collapsed_nodes_json") or "[]")
    except json.JSONDecodeError:
        flash("Dados de ordenação inválidos — tente novamente.", "error")
        return redirect(url_for("profile.menu_preferences"))

    sidebar_collapsed = bool(request.form.get("sidebar_collapsed"))

    menu_svc.save_user_preference(
        current_user.id,
        order_overrides=order_overrides,
        collapsed_nodes=collapsed_nodes,
        sidebar_collapsed=sidebar_collapsed,
    )
    flash("Suas preferências de menu foram salvas.", "success")
    return redirect(url_for("profile.menu_preferences"))
