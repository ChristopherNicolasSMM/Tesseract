"""
controller/core/designer.py

Páginas customizadas escritas à mão (Fase 12).

Histórico: este controller já foi o motor do Designer visual (canvas
drag-and-drop, paleta, painel de propriedades e, na Fase 11, árvore de
componentes com catálogo de propriedades). O construtor visual foi
REMOVIDO na Fase 12 por decisão de escopo — ver o docstring de
model/core/designer_page.py. Sobrou o que é estável e carrega o valor
real:

- CRUD de páginas customizadas (`/admin/designer/`)
- Editor do conteúdo HTML da página (`/admin/designer/<id>/edit`)
- Runtime da página publicada (`/designer/<slug>`)
- Substituição de tela do CrudGen no menu (`.../settings`, Fase 10)
- Execução server-side de Ação de Dado
  (`/admin/designer/data-action/<id>/execute`) — usada pelo JavaScript
  das páginas escritas à mão, e o único ponto que toca credencial de
  conexão OData.
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from core.odata.connection_manager import ODataConnectionManager
from model.core.designer_page import DesignerPage
from model.core.designer_data_action import DesignerDataAction

designer_bp = Blueprint("designer", __name__, url_prefix="/admin/designer")
designer_view_bp = Blueprint("designer_view", __name__, url_prefix="/designer")

_EXPORT_HEADERS = ["name", "slug", "is_published", "permission_required"]


def _slugify(name: str) -> str:
    base = re.sub(r"[^\w]+", "-", name.lower()).strip("-") or "pagina"
    slug = base
    n = 1
    while DesignerPage.query.filter_by(slug=slug).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


def _starter_html(name: str) -> str:
    """Conteúdo inicial de uma página nova — mínimo de propósito. O
    ponto de partida completo, com os componentes do NiceAdmin já no
    padrão do sistema, está em
    static/modelo_paginas_nice_admin/_modelo-pagina-customizada.html
    (linkado no editor)."""
    return (
        '<div class="row">\n'
        '  <div class="col-12">\n'
        '    <div class="card">\n'
        '      <div class="card-body">\n'
        f'        <h5 class="card-title">{name}</h5>\n'
        '        <p>Conteúdo da página. Edite este HTML no editor.</p>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
    )


def _search_query(search: str):
    query = DesignerPage.query.order_by(DesignerPage.name)
    if search:
        query = query.filter(DesignerPage.name.ilike(f"%{search}%"))
    return query


# ── Gestão de páginas ────────────────────────────────────────────────────────

@designer_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    pages_items, total, total_pages = paginate(_search_query(search), page)
    return render_template(
        "core/admin/designer_manage.html",
        designer_pages=pages_items, search=search, total=total, page=page, pages=total_pages,
    )


@designer_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    rows = [[p.name, p.slug, p.is_published, p.permission_required or ""]
            for p in _search_query(search).all()]
    return export_csv_response(_EXPORT_HEADERS, rows, "paginas_designer")


@designer_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    rows = [[p.name, p.slug, p.is_published, p.permission_required or ""]
            for p in _search_query(search).all()]
    return export_xlsx_response(_EXPORT_HEADERS, rows, "paginas_designer", "Páginas")


@designer_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nome da página é obrigatório.", "error")
        return redirect(url_for("designer.manage"))

    page = DesignerPage(
        name=name, title=name, slug=_slugify(name),
        created_by_user_id=current_user.id, content_html=_starter_html(name),
    )
    db.session.add(page)
    db.session.commit()
    flash(f"Página '{name}' criada.", "success")
    return redirect(url_for("designer.edit", page_id=page.id))


@designer_bp.route("/<int:page_id>/edit", methods=["GET"])
@login_required
@permission_required("admin")
def edit(page_id: int):
    page = DesignerPage.query.get(page_id)
    if not page:
        flash("Página não encontrada.", "error")
        return redirect(url_for("designer.manage"))
    return render_template(
        "core/admin/designer_editor.html",
        page=page,
        data_actions=DesignerDataAction.query.order_by(DesignerDataAction.name).all(),
    )


@designer_bp.route("/<int:page_id>/content", methods=["POST"])
@login_required
@permission_required("admin")
def save_content(page_id: int):
    page = DesignerPage.query.get(page_id)
    if not page:
        flash("Página não encontrada.", "error")
        return redirect(url_for("designer.manage"))

    page.content_html = request.form.get("content_html") or ""
    page.title = (request.form.get("title") or "").strip() or None
    db.session.commit()
    flash("Conteúdo salvo.", "success")
    return redirect(url_for("designer.edit", page_id=page.id))


@designer_bp.route("/<int:page_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(page_id: int):
    page = DesignerPage.query.get(page_id)
    if page:
        db.session.delete(page)
        db.session.commit()
        from core.designer_menu_override import resolve_designer_page_menu_overrides
        resolve_designer_page_menu_overrides()
        flash("Página excluída.", "success")
    return redirect(url_for("designer.manage"))


@designer_bp.route("/<int:page_id>/publish", methods=["POST"])
@login_required
@permission_required("admin")
def publish(page_id: int):
    page = DesignerPage.query.get(page_id)
    if not page:
        flash("Página não encontrada.", "error")
        return redirect(url_for("designer.manage"))
    page.is_published = not page.is_published
    db.session.commit()
    from core.designer_menu_override import resolve_designer_page_menu_overrides
    resolve_designer_page_menu_overrides()
    return redirect(url_for("designer.edit", page_id=page_id))


@designer_bp.route("/<int:page_id>/settings", methods=["POST"])
@login_required
@permission_required("admin")
def update_settings(page_id: int):
    """Substituição de tela do CrudGen no menu (Fase 10, Patch 6)."""
    page = DesignerPage.query.get(page_id)
    if not page:
        flash("Página não encontrada.", "error")
        return redirect(url_for("designer.manage"))

    page.permission_required = (request.form.get("permission_required") or "").strip() or None
    page.replaces_entity_key = (request.form.get("replaces_entity_key") or "").strip() or None
    replaces_view = (request.form.get("replaces_view") or "").strip()
    page.replaces_view = replaces_view if replaces_view in ("manage", "detail") else None
    page.replace_in_menu = request.form.get("replace_in_menu") == "on"
    db.session.commit()

    from core.designer_menu_override import resolve_designer_page_menu_overrides
    resolve_designer_page_menu_overrides()

    flash("Configurações da página salvas.", "success")
    return redirect(url_for("designer.edit", page_id=page.id))


# ── Execução de Ação de Dado (server-side) ───────────────────────────────────
# Único ponto que toca credencial de conexão OData: o JavaScript de uma
# página customizada chama este endpoint, nunca o provedor diretamente.

@designer_bp.route("/data-action/<int:action_id>/execute", methods=["POST"])
@login_required
def execute_data_action(action_id: int):
    action = DesignerDataAction.query.get(action_id)
    if not action:
        return jsonify(success=False, error="Ação de Dado não encontrada."), 404

    if action.permission_required and not current_user.has_permission(action.permission_required):
        return jsonify(success=False, error="Permissão necessária para executar esta ação."), 403

    body = request.get_json(silent=True) or {}
    manager = ODataConnectionManager(action.connection)

    try:
        if action.operation == "query":
            params = dict(action.static_params or {})
            params.update(body.get("params") or {})
            result = manager.query(action.entity_name, params)
        elif action.operation == "update":
            key = body.get("key")
            if not key:
                return jsonify(success=False, error="'key' é obrigatório para operation='update'."), 422
            result = manager.patch(action.entity_name, key, body.get("payload") or {})
        else:
            return jsonify(
                success=False,
                error=f"operation='{action.operation}' ainda não suportada pelo motor de execução.",
            ), 501
    except RuntimeError as exc:
        return jsonify(success=False, error=str(exc)), 502

    return jsonify(success=True, result=result)


# ── Runtime ──────────────────────────────────────────────────────────────────

@designer_view_bp.route("/<slug>", methods=["GET"])
@login_required
def view(slug: str):
    page = DesignerPage.query.filter_by(slug=slug).first()
    if not page or not page.is_published:
        abort(404)
    if page.permission_required and not current_user.has_permission(page.permission_required):
        abort(403)
    return render_template("core/designer_runtime.html", page=page)
