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
from model.core.designer_page import DesignerPage
from model.core.designer_component import DesignerComponent, COMPONENT_TYPES

designer_bp = Blueprint("designer", __name__, url_prefix="/admin/designer")
designer_view_bp = Blueprint("designer_view", __name__, url_prefix="/designer")

_DEFAULT_SIZE = {
    "heading": (600, 50),
    "label": (200, 30),
    "textbox": (280, 60),
    "button": (140, 40),
    "image": (200, 150),
    "divider": (600, 4),
}

_DEFAULT_PROPERTIES = {
    "heading": {"text": "Título", "font_size": 26, "text_color": "#012970", "bold": True},
    "label": {"text": "Texto"},
    "textbox": {"label": "Campo", "placeholder": "", "field_name": ""},
    "button": {"text": "Botão", "variant": "primary"},
    "image": {"src": "", "alt": ""},
    "divider": {"color": "#ced4da"},
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
    pages = DesignerPage.query.order_by(DesignerPage.name).all()
    return render_template("core/admin/designer_manage.html", pages=pages)


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
