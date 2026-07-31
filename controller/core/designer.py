"""
controller/core/designer.py

Designer visual (Fase 7c) — editor de páginas com drag-and-drop e a
tela de execução (runtime) que renderiza o que foi montado.

Edição (mover/redimensionar/editar propriedades) acontece via JS no
editor chamando os endpoints JSON aqui (`/admin/designer/component/...`)
— o canvas em si é HTML/CSS/JS puro, sem framework de frontend.
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user

from core.db import db
from core.permissions import permission_required
from core.admin_list_helpers import paginate, export_csv_response, export_xlsx_response
from core.actions_catalog import ACTION_CATALOG, EVENT_TYPES, get_action_def
from core.odata.connection_manager import ODataConnectionManager
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent, COMPONENT_TYPES
from model.core.designer_data_action import DesignerDataAction

designer_bp = Blueprint("designer", __name__, url_prefix="/admin/designer")
designer_view_bp = Blueprint("designer_view", __name__, url_prefix="/designer")

_DEFAULT_SIZE = {
    "heading": (600, 50),
    "label": (200, 30),
    "textbox": (280, 60),
    "button": (140, 40),
    "image": (200, 150),
    "divider": (600, 4),
    "select": (280, 60),
    "checkbox": (220, 30),
    "radio": (280, 100),
    "form_container": (420, 320),
    "datagrid": (600, 320),
}

_DEFAULT_PROPERTIES = {
    "heading": {"text": "Título", "font_size": 26, "text_color": "#012970", "bold": True},
    "label": {"text": "Texto"},
    "textbox": {"label": "Campo", "placeholder": "", "field_name": ""},
    "button": {"text": "Botão", "variant": "primary"},
    "image": {"src": "", "alt": ""},
    "divider": {"color": "#ced4da"},
    # options_source: "static" (usa static_options) ou "data_action"
    # (busca via Ação de Dado, casando value_field/label_field nas
    # colunas do registro retornado).
    "select": {
        "label": "Selecione", "field_name": "",
        "options_source": "static", "static_options": "Opção 1,Opção 2",
        "data_action_id": "", "value_field": "id", "label_field": "name",
    },
    "checkbox": {"label": "Marcar", "field_name": "", "checked_default": "false"},
    "radio": {"label": "Escolha", "field_name": "", "options": "Opção 1,Opção 2", "default_value": ""},
    # key_param: nome do parâmetro de query string da URL (?id=42) que
    # informa qual registro carregar — sempre filtra pela coluna "id"
    # (skill 02: PK é sempre Integer chamada "id" em todo model).
    "form_container": {"title": "Formulário", "data_action_id": "", "key_param": "id"},
    # columns vazio = usa todas as colunas do primeiro registro
    # retornado (exceto is_deleted/deleted_at).
    "datagrid": {"data_action_id": "", "columns": "", "title": "Lista"},
}


def _slugify(name: str) -> str:
    base = re.sub(r"[^\w]+", "-", name.lower()).strip("-") or "pagina"
    slug = base
    n = 1
    while DesignerPage.query.filter_by(slug=slug).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


# ── Gestão de páginas ────────────────────────────────────────────────────────

@designer_bp.route("/", methods=["GET"])
@login_required
@permission_required("admin")
def manage():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)

    query = DesignerPage.query.order_by(DesignerPage.name)
    if search:
        query = query.filter(DesignerPage.name.ilike(f"%{search}%"))

    pages_items, total, total_pages = paginate(query, page)
    return render_template(
        "core/admin/designer_manage.html",
        designer_pages=pages_items, search=search, total=total, page=page, pages=total_pages,
    )


@designer_bp.route("/export.csv", methods=["GET"])
@login_required
@permission_required("admin")
def export_csv():
    search = (request.args.get("q") or "").strip()
    query = DesignerPage.query.order_by(DesignerPage.name)
    if search:
        query = query.filter(DesignerPage.name.ilike(f"%{search}%"))
    rows = [[p.name, p.slug, p.is_published, len(p.components)] for p in query.all()]
    return export_csv_response(["name", "slug", "is_published", "componentes"], rows, "paginas_designer")


@designer_bp.route("/export.xlsx", methods=["GET"])
@login_required
@permission_required("admin")
def export_xlsx():
    search = (request.args.get("q") or "").strip()
    query = DesignerPage.query.order_by(DesignerPage.name)
    if search:
        query = query.filter(DesignerPage.name.ilike(f"%{search}%"))
    rows = [[p.name, p.slug, p.is_published, len(p.components)] for p in query.all()]
    return export_xlsx_response(["name", "slug", "is_published", "componentes"], rows, "paginas_designer", "Páginas")


@designer_bp.route("/", methods=["POST"])
@login_required
@permission_required("admin")
def create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nome da página é obrigatório.", "error")
        return redirect(url_for("designer.manage"))

    page = DesignerPage(name=name, title=name, slug=_slugify(name), created_by_user_id=current_user.id)
    db.session.add(page)
    db.session.commit()
    flash(f"Página '{name}' criada.", "success")
    return redirect(url_for("designer.edit", page_id=page.id))


@designer_bp.route("/<int:page_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete(page_id: int):
    page = DesignerPage.query.get(page_id)
    if page:
        db.session.delete(page)
        db.session.commit()
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
    return redirect(url_for("designer.edit", page_id=page_id))


# ── Editor ───────────────────────────────────────────────────────────────────

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
        page=page, component_types=COMPONENT_TYPES,
        action_catalog=ACTION_CATALOG, event_types=EVENT_TYPES,
        data_actions=DesignerDataAction.query.order_by(DesignerDataAction.name).all(),
        components_json=[c.to_dict() for c in page.components],
    )


@designer_bp.route("/<int:page_id>/components", methods=["POST"])
@login_required
@permission_required("admin")
def add_component(page_id: int):
    page = DesignerPage.query.get(page_id)
    if not page:
        return jsonify(success=False, error="Página não encontrada."), 404

    comp_type = request.json.get("type") if request.is_json else request.form.get("type")
    if comp_type not in COMPONENT_TYPES:
        return jsonify(success=False, error=f"Tipo de componente inválido: {comp_type}"), 422

    width, height = _DEFAULT_SIZE.get(comp_type, (150, 40))
    max_z = max([c.z_index for c in page.components], default=0)

    component = DesignerComponent(
        page_id=page.id, type=comp_type, name=f"{comp_type}_{len(page.components) + 1}",
        x=40, y=40, width=width, height=height, z_index=max_z + 1,
        properties=dict(_DEFAULT_PROPERTIES.get(comp_type, {})),
    )
    db.session.add(component)
    db.session.commit()
    return jsonify(success=True, component=component.to_dict())


@designer_bp.route("/component/<int:component_id>", methods=["POST"])
@login_required
@permission_required("admin")
def update_component(component_id: int):
    """Chamado pelo JS do editor a cada drag/resize/edição de propriedade."""
    component = DesignerComponent.query.get(component_id)
    if not component:
        return jsonify(success=False, error="Componente não encontrado."), 404

    data = request.get_json(silent=True) or {}
    for field in ("x", "y", "width", "height", "z_index"):
        if field in data:
            try:
                setattr(component, field, int(data[field]))
            except (TypeError, ValueError):
                return jsonify(success=False, error=f"{field} deve ser numérico."), 422

    if "properties" in data and isinstance(data["properties"], dict):
        component.properties = data["properties"]
    if "rules" in data and isinstance(data["rules"], list):
        component.rules = data["rules"]
    if "events" in data and isinstance(data["events"], dict):
        for event_name, actions in data["events"].items():
            if event_name not in EVENT_TYPES or not isinstance(actions, list):
                return jsonify(success=False, error=f"Evento inválido: {event_name}."), 422
            for action in actions:
                if not isinstance(action, dict) or get_action_def(action.get("action_type")) is None:
                    return jsonify(success=False, error=f"Tipo de ação inválido: {action}."), 422
        component.events = data["events"]
    if "name" in data:
        component.name = str(data["name"])[:100]

    db.session.commit()
    return jsonify(success=True, component=component.to_dict())


@designer_bp.route("/component/<int:component_id>/delete", methods=["POST"])
@login_required
@permission_required("admin")
def delete_component(component_id: int):
    component = DesignerComponent.query.get(component_id)
    if component:
        db.session.delete(component)
        db.session.commit()
    return jsonify(success=True)


# ── Execução de Ação de Dado (única peça server-side do motor de Ações) ──────
# Decisão registrada em BACKLOG.md, Fase 10: toda Ação que toca dado/API
# roda sempre no servidor — o navegador só manda qual Ação de Dado disparar
# e, se for update, a chave/payload; quem decide a conexão/credencial é
# sempre este endpoint. Só @login_required (não @permission_required
# "admin") porque é chamado a partir de PÁGINAS PUBLICADAS em runtime,
# não só do editor — o controle de acesso de verdade é o
# `permission_required` da própria DesignerDataAction (ou público, se
# não configurado), igual já funciona para DesignerPage.
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
            # create/delete: schema já prevê (Patch 1), mas
            # ODataConnectionManager ainda não tem query()/patch()
            # equivalentes (nem para conexão externa) — não finjo que
            # funciona, devolvo 501 explícito em vez de tentar e
            # quebrar de um jeito confuso pro autor da página.
            return jsonify(success=False, error=f"operation='{action.operation}' ainda não suportada pelo motor de execução."), 501
    except RuntimeError as exc:
        return jsonify(success=False, error=str(exc)), 502

    return jsonify(success=True, result=result)


# ── Execução (runtime) ──────────────────────────────────────────────────────

@designer_view_bp.route("/<slug>", methods=["GET"])
@login_required
def view(slug: str):
    page = DesignerPage.query.filter_by(slug=slug).first()
    if not page or not page.is_published:
        abort(404)

    if page.permission_required and not current_user.has_permission(page.permission_required):
        abort(403)

    return render_template("core/designer_runtime.html", page=page)
