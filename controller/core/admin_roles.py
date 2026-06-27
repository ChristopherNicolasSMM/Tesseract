"""
controller/core/admin_roles.py

Telas HTML de gestão de Role/Permission (RBAC). Permission nunca é
criada por aqui — "código lidera, banco segue" (skill 00/03): a UI só
LÊ Permissions já sincronizadas (Camada 1 automática + Camada 2 via
@permission) e associa a um Role. Role, por sua vez, é criado livremente
pela UI (não é "código que lidera" — Role é organizacional, não técnico).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from model.core.role import Role
from model.core.permission import Permission

admin_roles_bp = Blueprint("admin_roles", __name__, url_prefix="/admin/roles")

_EXPORT_HEADERS = ["name", "description", "permissoes", "usuarios"]


def _filtered_query(search: str):
    query = Role.query.order_by(Role.name)
    if search:
        like = f"%{search}%"
        query = query.filter(Role.name.ilike(like) | Role.description.ilike(like))
    return query


def _permissions_grouped_by_module():
    """
    Agrupa Permission por "módulo" (a parte antes do primeiro ponto do
    nome, ex.: "yeast_strains.create" -> grupo "yeast_strains") — só
    para a UI ficar navegável com 100+ permissões; não é um conceito
    persistido em lugar nenhum.
    """
    from collections import OrderedDict
    perms = Permission.query.order_by(Permission.name).all()
    grouped = OrderedDict()
    for p in perms:
        group = p.name.split(".")[0]
        grouped.setdefault(group, []).append(p)
    return grouped


@admin_roles_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    roles, total, pages = paginate(_filtered_query(search), page)
    return render_template(
        "core/admin/roles_manage.html",
        roles=roles, search=search, total=total, page=page, pages=pages,
    )


@admin_roles_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    rows = [[r.name, r.description, len(r.permissions), len(r.users)] for r in _filtered_query(search).all()]
    return export_csv_response(_EXPORT_HEADERS, rows, "roles")


@admin_roles_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    rows = [[r.name, r.description, len(r.permissions), len(r.users)] for r in _filtered_query(search).all()]
    return export_xlsx_response(_EXPORT_HEADERS, rows, "roles", "Roles")


@admin_roles_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None

    if not name:
        flash("Nome do Role é obrigatório.", "error")
        return redirect(url_for("admin_roles.manage"))

    if Role.query.filter_by(name=name).first():
        flash(f"Já existe um Role com o nome '{name}'.", "error")
        return redirect(url_for("admin_roles.manage"))

    role = Role(name=name, description=description)
    db.session.add(role)
    db.session.commit()
    flash(f"Role '{name}' criado.", "success")
    return redirect(url_for("admin_roles.detail", role_id=role.id))


@admin_roles_bp.route("/<int:role_id>", methods=["GET"])
@login_required
@permission_required("admin")
def detail(role_id: int):
    role = Role.query.get(role_id)
    if not role:
        flash("Role não encontrado.", "error")
        return redirect(url_for("admin_roles.manage"))
    return render_template(
        "core/admin/roles_detail.html",
        role=role,
        permissions_grouped=_permissions_grouped_by_module(),
    )


@admin_roles_bp.route("/<int:role_id>", methods=["POST"])
@login_required
@permission_required("admin")
def update(role_id: int):
    role = Role.query.get(role_id)
    if not role:
        flash("Role não encontrado.", "error")
        return redirect(url_for("admin_roles.manage"))

    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nome do Role é obrigatório.", "error")
        return redirect(url_for("admin_roles.detail", role_id=role_id))

    existing = Role.query.filter_by(name=name).first()
    if existing and existing.id != role.id:
        flash(f"Já existe outro Role com o nome '{name}'.", "error")
        return redirect(url_for("admin_roles.detail", role_id=role_id))

    role.name = name
    role.description = (request.form.get("description") or "").strip() or None
    db.session.commit()
    flash("Role atualizado.", "success")
    return redirect(url_for("admin_roles.detail", role_id=role_id))


@admin_roles_bp.route("/<int:role_id>/permissions", methods=["POST"])
@login_required
@permission_required("admin")
def update_permissions(role_id: int):
    role = Role.query.get(role_id)
    if not role:
        flash("Role não encontrado.", "error")
        return redirect(url_for("admin_roles.manage"))

    selected_ids = {int(pid) for pid in request.form.getlist("permission_ids")}
    role.permissions = Permission.query.filter(Permission.id.in_(selected_ids)).all() if selected_ids else []
    db.session.commit()
    flash("Permissões atualizadas.", "success")
    return redirect(url_for("admin_roles.detail", role_id=role_id))


@admin_roles_bp.route("/<int:role_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(role_id: int):
    role = Role.query.get(role_id)
    if not role:
        flash("Role não encontrado.", "error")
        return redirect(url_for("admin_roles.manage"))

    if role.users:
        flash(
            f"Não é possível excluir: {len(role.users)} usuário(s) ainda têm "
            f"este Role atribuído. Remova a atribuição primeiro.",
            "error",
        )
        return redirect(url_for("admin_roles.detail", role_id=role_id))

    db.session.delete(role)
    db.session.commit()
    flash("Role excluído.", "success")
    return redirect(url_for("admin_roles.manage"))
