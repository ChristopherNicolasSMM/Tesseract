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

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
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
    {"key": "sessions", "label": "Sessões", "icon": "bi-collection-play", "enabled": True},
    {"key": "plant", "label": "Planta", "icon": "bi-diagram-3", "enabled": True},
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


@plant_workspace_bp.route("/<int:plant_id>/tab/sessions", methods=["GET"])
@login_required
@permission_required("brew_sessions.list")
def tab_sessions(plant_id: int):
    """Aba Sessões (conversa): consolida Sessões de Brassagem + Passos
    da Sessão (visão ENXUTA, só acompanhamento — não é o CRUD completo
    de `brew_session_steps`, de propósito) + Logs + Alarmes recentes.

    "Adicionar Etapa" aqui não abre um popup de edição de verdade
    ainda (isso mora na receita-modelo, não na sessão — mesma regra do
    step_card do Dashboard) — leva pro editor de timeline completo
    (`recipe_timeline`) numa aba nova, até a aba "Receita Mash" deste
    workspace existir (fase futura)."""
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    sessions = (
        BrewSession.query.filter_by(plant_id=plant_id, is_deleted=False)
        .order_by(BrewSession.id.desc())
        .limit(20)
        .all()
    )

    session_id = request.args.get("session_id", type=int)
    selected_session = None
    if session_id:
        selected_session = next((s for s in sessions if s.id == session_id), None)
    if selected_session is None and sessions:
        selected_session = (
            next((s for s in sessions if s.status == "active"), None) or sessions[0]
        )

    steps, logs, alarms = [], [], []
    if selected_session:
        steps = (
            BrewSessionStep.query.filter_by(session_id=selected_session.id, is_deleted=False)
            .order_by(BrewSessionStep.step_index)
            .all()
        )
        logs = (
            BrewSessionLog.query.filter_by(session_id=selected_session.id, is_deleted=False)
            .order_by(BrewSessionLog.created_at.desc())
            .limit(20)
            .all()
        )
        alarms = (
            BrewSessionAlarm.query.filter_by(session_id=selected_session.id, is_deleted=False)
            .order_by(BrewSessionAlarm.created_at.desc())
            .limit(20)
            .all()
        )

    return render_template(
        "plant_workspace/_tab_sessions.html",
        plant=plant, sessions=sessions, selected_session=selected_session,
        steps=steps, logs=logs, alarms=alarms,
    )


@plant_workspace_bp.route("/<int:plant_id>/tab/plant", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def tab_plant(plant_id: int):
    """Aba Planta (conversa): consolida os dados da própria Planta +
    Tanques + Mapeamentos de Planta. Mesmo padrão enxuto da aba
    Sessões — lista/mostra aqui, edição de verdade continua na tela
    cheia de cada entidade (link "abrir em nova aba")."""
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    vessels = (
        BrewPlantVessel.query.filter_by(plant_id=plant_id, is_deleted=False)
        .order_by(BrewPlantVessel.position_order, BrewPlantVessel.id)
        .all()
    )
    vessel_ids = [v.id for v in vessels]
    mappings = []
    if vessel_ids:
        mappings = (
            BrewPlantMapping.query.filter(
                BrewPlantMapping.vessel_id.in_(vessel_ids), BrewPlantMapping.is_deleted == False,  # noqa: E712
            )
            .order_by(BrewPlantMapping.vessel_id)
            .all()
        )
    vessels_by_id = {v.id: v for v in vessels}

    return render_template(
        "plant_workspace/_tab_plant.html",
        plant=plant, vessels=vessels, mappings=mappings, vessels_by_id=vessels_by_id,
    )
