"""
addons/addon_brewstation/features/feature_mash_control/controller/recipe_timeline.py

"Importar Receita para Brassar" (conversa — timeline única de etapas
e alertas): escolhe uma MashRecipe já cadastrada, vê/edita a timeline
inteira (RecipeStep — mostura+fervura+alerta, com lupulagem
auto-derivada), e gera a Sessão (rascunho ou já iniciando).

NÃO é gerado pelo CrudGen — mesmo padrão de dashboard_runtime.py.
"""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service as svc

recipe_timeline_bp = Blueprint(
    "recipe_timeline", __name__, url_prefix="/brewstation/recipe-timeline"
)


@recipe_timeline_bp.route("/", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def picker():
    recipes = MashRecipe.query.filter_by(is_deleted=False, is_active=True).order_by(MashRecipe.name).all()
    return render_template("recipe_timeline/picker.html", recipes=recipes)


@recipe_timeline_bp.route("/<int:recipe_id>", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def view(recipe_id: int):
    recipe = MashRecipe.query.get(recipe_id)
    if not recipe or recipe.is_deleted:
        flash("Receita não encontrada.", "error")
        return redirect(url_for("recipe_timeline.picker"))

    sync_result = svc.sync_hop_alerts(recipe)
    if sync_result["created"]:
        flash(f"Alertas de lupulagem criados automaticamente: {', '.join(sync_result['created'])}", "success")

    timeline = svc.get_timeline(recipe_id)
    plants = BrewPlant.query.filter_by(is_deleted=False).order_by(BrewPlant.name).all()

    return render_template(
        "recipe_timeline/view.html",
        recipe=recipe, timeline=timeline, plants=plants,
    )


@recipe_timeline_bp.route("/<int:recipe_id>/steps", methods=["POST"])
@login_required
@permission_required("recipe_steps.create")
def add_step(recipe_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        step = svc.add_step(
            recipe_id, step_type=payload.get("step_type"), nome=payload.get("nome") or "",
            temperatura=payload.get("temperatura"), tempo_min=payload.get("tempo_min"),
            ramp_time_min=payload.get("ramp_time_min"), tipo=payload.get("tipo"),
            trigger_minutes_remaining=payload.get("trigger_minutes_remaining"),
            parent_step_id=payload.get("parent_step_id"),
        )
    except svc.RecipeTimelineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "step_id": step.id})


@recipe_timeline_bp.route("/<int:recipe_id>/steps.json", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def steps_json(recipe_id: int):
    """Timeline em JSON — usado pelo modal de etapas embutido no
    Dashboard de Brassagem (conversa, Ponto 2: reaproveitar o mesmo
    formulário de add/editar etapa sem sair da tela de operação, em
    vez de renderizar a página HTML inteira de novo)."""
    recipe = MashRecipe.query.get(recipe_id)
    if not recipe or recipe.is_deleted:
        return jsonify({"error": "Receita não encontrada."}), 404
    timeline = svc.get_timeline(recipe_id)
    return jsonify({"steps": [
        {
            "id": s.id, "step_type": s.step_type, "nome": s.nome,
            "temperatura": s.temperatura, "tempo_min": s.tempo_min,
            "ramp_time_min": s.ramp_time_min, "trigger_minutes_remaining": s.trigger_minutes_remaining,
            "source": s.source,
        }
        for s in timeline
    ]})


@recipe_timeline_bp.route("/steps/<int:step_id>", methods=["POST"])
@login_required
@permission_required("recipe_steps.update")
def update_step(step_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        svc.update_step(step_id, **payload)
    except svc.RecipeTimelineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True})


@recipe_timeline_bp.route("/steps/<int:step_id>/delete", methods=["POST"])
@login_required
@permission_required("recipe_steps.trash")
def delete_step(step_id: int):
    svc.remove_step(step_id)
    return jsonify({"ok": True})


@recipe_timeline_bp.route("/<int:recipe_id>/steps/reorder", methods=["POST"])
@login_required
@permission_required("recipe_steps.update")
def reorder_steps(recipe_id: int):
    payload = request.get_json(silent=True) or {}
    svc.reorder_steps(recipe_id, payload.get("ordered_ids") or [])
    return jsonify({"ok": True})


@recipe_timeline_bp.route("/<int:recipe_id>/resync-hop-alerts", methods=["POST"])
@login_required
@permission_required("recipe_steps.update")
def resync_hop_alerts(recipe_id: int):
    recipe = MashRecipe.query.get(recipe_id)
    if not recipe or recipe.is_deleted:
        return jsonify({"ok": False, "error": "Receita não encontrada."}), 404
    result = svc.sync_hop_alerts(recipe)
    return jsonify({"ok": True, **result})


@recipe_timeline_bp.route("/<int:recipe_id>/generate-session", methods=["POST"])
@login_required
@permission_required("brew_sessions.create")
def generate_session(recipe_id: int):
    plant_id = request.form.get("plant_id", type=int)
    name = (request.form.get("name") or "").strip()
    status = request.form.get("status") or "draft"

    if not plant_id or not name:
        flash("Planta e nome da sessão são obrigatórios.", "error")
        return redirect(url_for("recipe_timeline.view", recipe_id=recipe_id))

    try:
        session = svc.generate_session_from_recipe(
            recipe_id, plant_id=plant_id, name=name, status=status,
            created_by_user_id=current_user.id if current_user.is_authenticated else None,
        )
    except svc.RecipeTimelineError as exc:
        flash(str(exc), "error")
        return redirect(url_for("recipe_timeline.view", recipe_id=recipe_id))

    flash(f"Sessão '{session.name}' gerada com sucesso ({session.status}).", "success")
    return redirect(url_for("brew_sessions.detail", id=session.id))
