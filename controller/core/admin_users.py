"""
controller/core/admin_users.py

Telas HTML de administração de usuários — reaproveita a validação e
aplicação de payload já existentes em api/routes/core/admin/users.py
(_validate_payload/_apply_payload), em vez de duplicar a lógica.

Inclui o que a API por si só não cobria visualmente: atribuição de
Role (RBAC) e reset de senha pelo admin (BACKLOG.md — "admin deve ter
cláusula para retornar ao estado com senha padrão").
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from model.core.user import User
from model.core.role import Role
from api.routes.core.admin.users import _validate_payload, _apply_payload

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")

_EXPORT_HEADERS = ["username", "nome_completo", "email", "is_active", "is_admin"]


def _filtered_query(search: str):
    query = User.query.order_by(User.username)
    if search:
        like = f"%{search}%"
        query = query.filter(
            User.username.ilike(like) | User.nome_completo.ilike(like) | User.email.ilike(like)
        )
    return query


@admin_users_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    users, total, pages = paginate(_filtered_query(search), page)
    return render_template(
        "core/admin/users_manage.html",
        users=users, search=search, total=total, page=page, pages=pages,
    )


@admin_users_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    rows = [[u.username, u.nome_completo, u.email, u.is_active, u.is_admin] for u in _filtered_query(search).all()]
    return export_csv_response(_EXPORT_HEADERS, rows, "usuarios")


@admin_users_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    rows = [[u.username, u.nome_completo, u.email, u.is_active, u.is_admin] for u in _filtered_query(search).all()]
    return export_xlsx_response(_EXPORT_HEADERS, rows, "usuarios", "Usuários")


@admin_users_bp.route("/<int:user_id>", methods=["GET"])
@login_required
@permission_required("admin")
def detail(user_id: int):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))
    all_roles = Role.query.order_by(Role.name).all()
    return render_template(
        "core/admin/users_detail.html",
        user=user, all_roles=all_roles,
    )


@admin_users_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    data = request.form.to_dict()
    errors = _validate_payload(data, is_update=False)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("admin_users.manage"))

    user = User(is_active=True, is_admin=bool(data.get("is_admin")))
    try:
        _apply_payload(user, data, is_update=False)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin_users.manage"))

    db.session.add(user)
    db.session.commit()
    flash(f"Usuário '{user.username}' criado.", "success")
    return redirect(url_for("admin_users.manage"))


@admin_users_bp.route("/<int:user_id>", methods=["POST"])
@login_required
@permission_required("admin")
def update(user_id: int):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))

    data = request.form.to_dict()
    data["is_admin"] = "is_admin" in request.form  # checkbox: ausente = False
    errors = _validate_payload(data, is_update=True, current_user_id=user.id)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    # Senha em branco no formulário de edição = não trocar (diferente da
    # API JSON, onde "password" ausente já tem esse efeito por padrão).
    if not data.get("password"):
        data.pop("password", None)

    try:
        _apply_payload(user, data, is_update=True)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    db.session.commit()
    flash("Dados salvos.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))


@admin_users_bp.route("/<int:user_id>/deactivate", methods=["POST"])
@login_required
@permission_required("admin")
def deactivate(user_id: int):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))

    if user.id == current_user.id:
        # UserMixin.is_authenticated == self.is_active (Flask-Login) —
        # desativar a própria conta logada desautentica na próxima
        # requisição (ver BACKLOG.md, Fase 2). Bloqueado aqui na UI
        # para não confundir o admin; via API isso ainda é possível
        # de propósito (outro admin pode desativar alguém, inclusive
        # a própria sessão de outro terminal).
        flash("Você não pode desativar sua própria conta enquanto estiver logado com ela.", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    user.is_active = False
    db.session.commit()
    flash(f"Usuário '{user.username}' desativado.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))


@admin_users_bp.route("/<int:user_id>/activate", methods=["POST"])
@login_required
@permission_required("admin")
def activate(user_id: int):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))
    user.is_active = True
    db.session.commit()
    flash(f"Usuário '{user.username}' ativado.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))


@admin_users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@login_required
@permission_required("admin")
def reset_password(user_id: int):
    """
    Reset de senha pelo admin, direto na tela — caminho mais rápido
    que o CLI (`flask reset-password`) para quando o admin já está
    logado e só precisa resolver "esqueci minha senha" de outro
    usuário sem abrir terminal.
    """
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))

    new_password = (request.form.get("new_password") or "").strip()
    if len(new_password) < 6:
        flash("A nova senha deve ter pelo menos 6 caracteres.", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    user.set_password(new_password)
    db.session.commit()
    flash(f"Senha de '{user.username}' redefinida.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))


@admin_users_bp.route("/<int:user_id>/roles", methods=["POST"])
@login_required
@permission_required("admin")
def update_roles(user_id: int):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for("admin_users.manage"))

    selected_ids = {int(rid) for rid in request.form.getlist("role_ids")}
    user.roles = Role.query.filter(Role.id.in_(selected_ids)).all() if selected_ids else []
    db.session.commit()
    flash("Papéis atualizados.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))
