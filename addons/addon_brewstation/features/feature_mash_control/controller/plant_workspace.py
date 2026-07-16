"""
addons/addon_brewstation/features/feature_mash_control/controller/plant_workspace.py

Workspace consolidado por Planta (conversa — "juntar Dashboard + Etapas
+ Sessões + Planta numa tela só"). NÃO gerado pelo CrudGen — mesmo
espírito de dashboard_runtime.py/automation_engine.py: ponto de
extensão manual estável.

Arquitetura decidida em conversa:
- Escolhe/cria uma Planta primeiro (`/plant-workspace/`) — tudo daqui
  pra frente é escopado por ela.
- Abas de verdade (fragmento HTML buscado via AJAX, sem iframe) — cada
  aba precisa de uma rota própria devolvendo só o conteúdo, sem o
  layout do Core em volta (`core/base.html`).
- Fase 1 (este commit): casca (seletor/criação de Planta + barra de
  abas) + aba Dashboard funcionando. As demais abas (Sessões, Planta,
  Receita Mash, Automação) entram em rodadas seguintes — aparecem na
  barra já, desabilitadas ("em breve").
- As telas antigas (menu "Controle de Mostura" de hoje) continuam
  existindo em paralelo — a remoção do menu é decisão pra depois de
  validar o workspace na prática (registrado em conversa).
"""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.controller.dashboard_runtime import (
    _build_dashboard_view_context,
)

plant_workspace_bp = Blueprint(
    "plant_workspace", __name__, url_prefix="/brewstation/plant-workspace"
)

# Abas da fase 1 — só "dashboard" tem rota de fragmento real ainda.
_TABS = [
    {"key": "dashboard", "label": "Dashboard", "icon": "bi-speedometer2", "enabled": True},
    {"key": "sessions", "label": "Sessões", "icon": "bi-collection-play", "enabled": False},
    {"key": "plant", "label": "Planta", "icon": "bi-diagram-3", "enabled": False},
    {"key": "recipe", "label": "Receita Mash", "icon": "bi-journal-text", "enabled": False},
    {"key": "automation", "label": "Automação", "icon": "bi-lightning-charge", "enabled": False},
]


@plant_workspace_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def landing():
    """Escolher (ou ir criar) a Planta antes de entrar no workspace."""
    plants = BrewPlant.query.filter_by(is_deleted=False).order_by(BrewPlant.name).all()
    return render_template("plant_workspace/landing.html", plants=plants)


@plant_workspace_bp.route("/<int:plant_id>", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def shell(plant_id: int):
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        flash("Planta não encontrada.", "error")
        return redirect(url_for("plant_workspace.landing"))
    return render_template("plant_workspace/shell.html", plant=plant, tabs=_TABS)


@plant_workspace_bp.route("/<int:plant_id>/tab/dashboard", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def tab_dashboard(plant_id: int):
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    layout = (
        DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False, is_default=True).first()
        or DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False).order_by(DashboardLayout.id).first()
    )
    if not layout:
        return render_template("plant_workspace/_tab_dashboard_empty.html", plant=plant)

    context = _build_dashboard_view_context(layout, is_fragment=True)
    # Dentro do workspace, o seletor de layouts (ver _content.html) só
    # deve listar os da PRÓPRIA planta — a tela cheia continua listando
    # todos os layouts do sistema (comportamento inalterado).
    context["all_layouts"] = (
        DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False).order_by(DashboardLayout.name).all()
    )
    return render_template("dashboards/_fragment.html", **context)
