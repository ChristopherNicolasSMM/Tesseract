"""
addons/addon_brewstation/features/feature_mash_control/controller/plant_workspace.py

Workspace consolidado por Planta (Dashboard, sessões, configuração,
receita e automação). NÃO gerado pelo CrudGen — mesmo
espírito de dashboard_runtime.py/automation_engine.py: ponto de
extensão manual estável.

Arquitetura decidida em conversa:
- Escolhe/cria uma Planta primeiro (`/plant-workspace/`) — tudo daqui
  pra frente é escopado por ela.
- Abas de verdade (fragmento HTML buscado via AJAX, sem iframe) — cada
  aba precisa de uma rota própria devolvendo só o conteúdo, sem o
  layout do Core em volta (`core/base.html`).
- As cinco abas já possuem fragmentos. Cadastro e edição avançada ainda
  reaproveitam as rotas próprias de cada entidade.
- As telas de edição e histórico continuam disponíveis no menu; três
  atalhos de visualização duplicados pelo workspace ficam ocultos.
"""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from core.permissions import permission_required
from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule_log import AutomationRuleLog
from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
from addons.addon_brewstation.features.feature_mash_control.model.recipe_ingredient import RecipeIngredient
from addons.addon_brewstation.features.feature_mash_control.model.fermentation_step import FermentationStep
from addons.addon_brewstation.features.feature_mash_control.model.water_profile import WaterProfile
from addons.addon_brewstation.features.feature_mash_control.model.recipe_history import RecipeHistory
from addons.addon_brewstation.features.feature_mash_control.services.ingredient_consumption_service import (
    conferir_ingredientes, calcular_custo_insumos_receita,
)
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_service import BrewPlantService
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_vessel_service import BrewPlantVesselService
from addons.addon_brewstation.features.feature_mash_control.services.brew_plant_mapping_service import BrewPlantMappingService
from addons.addon_device_manager.root.services.device_function_lookup import (
    get_function_by_name, list_functions_for_mapping,
)
from addons.addon_brewstation.features.feature_mash_control.services.dashboard_layout_service import DashboardLayoutService
from addons.addon_brewstation.features.feature_mash_control.services.brew_session_service import BrewSessionService
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_consumption_service
from addons.addon_brewstation.features.feature_mash_control.services.session_alarm_actions import (
    acknowledge_alarm, SessionAlarmNotFound,
)
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_mash_control.controller.dashboard_runtime import (
    _build_dashboard_view_context,
)
from addons.addon_brewstation.features.feature_mash_control.controller.recipe_timeline import (
    _build_recipe_view_context,
)

plant_workspace_bp = Blueprint(
    "plant_workspace", __name__, url_prefix="/brewstation/plant-workspace"
)

# Abas do workspace.
_TABS = [
    {"key": "dashboard", "label": "Dashboard", "icon": "bi-speedometer2", "enabled": True},
    {"key": "sessions", "label": "Sessões", "icon": "bi-collection-play", "enabled": True},
    {"key": "plant", "label": "Planta", "icon": "bi-diagram-3", "enabled": True},
    {"key": "recipe", "label": "Receita Mash", "icon": "bi-journal-text", "enabled": True},
    {"key": "automation", "label": "Automação", "icon": "bi-lightning-charge", "enabled": True},
]


@plant_workspace_bp.route("/", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def landing():
    """Escolher (ou ir criar) a Planta antes de entrar no workspace."""
    plants = BrewPlant.query.filter_by(is_deleted=False).order_by(BrewPlant.name).all()
    requested_tab = request.args.get("tab", "dashboard")
    initial_tab = requested_tab if requested_tab in {t["key"] for t in _TABS} else "dashboard"
    return render_template("plant_workspace/landing.html", plants=plants, initial_tab=initial_tab)


@plant_workspace_bp.route("/", methods=["POST"])
@login_required
@permission_required("brew_plants.create")
def create_plant():
    name = (request.form.get("name") or "").strip()
    if not name or len(name) > 100:
        flash("Informe um nome de planta com até 100 caracteres.", "error")
        return redirect(url_for("plant_workspace.landing"))
    result = BrewPlantService().create({"name": name})
    if not result.success:
        flash(result.error, "error")
        return redirect(url_for("plant_workspace.landing"))
    return redirect(url_for("plant_workspace.shell", plant_id=result.data.id, tab="plant"))


def _workspace_form_result(result, *, plant_id: int, tab: str, status: int = 201):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not result.success:
            return jsonify({"ok": False, "error": result.error}), result.code
        plant = db.session.get(BrewPlant, plant_id)
        return jsonify({"ok": True, "id": result.data.id, "plant_name": plant.name if plant else None}), status
    flash("Cadastro realizado." if result.success else result.error,
          "success" if result.success else "error")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab=tab))


@plant_workspace_bp.route("/<int:plant_id>/edit", methods=["POST"])
@login_required
@permission_required("brew_plants.update")
def update_plant(plant_id):
    plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first()
    if not plant:
        return _workspace_form_error("Planta não encontrada.", 404, plant_id=plant_id, tab="plant")
    name = (request.form.get("name") or "").strip()
    capacity = (request.form.get("capacity_liters") or "").strip()
    try:
        import math
        capacity = float(capacity.replace(",", ".")) if capacity else None
        if capacity is not None and (not math.isfinite(capacity) or capacity <= 0):
            raise ValueError
    except ValueError:
        return _workspace_form_error("Informe uma capacidade positiva ou deixe em branco.", 400, plant_id=plant_id, tab="plant")
    if not name or len(name) > 100:
        return _workspace_form_error("Informe um nome de planta com até 100 caracteres.", 400, plant_id=plant_id, tab="plant")
    result = BrewPlantService().update(plant_id, {"name": name,
        "description": (request.form.get("description") or "").strip(),
        "capacity_liters": capacity, "is_active": request.form.get("is_active") == "on"})
    return _workspace_form_result(result, plant_id=plant_id, tab="plant", status=200)


@plant_workspace_bp.route("/<int:plant_id>/vessels/<int:vessel_id>/edit", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.update")
def update_vessel(plant_id, vessel_id):
    vessel = (BrewPlantVessel.query.join(BrewPlant)
              .filter(BrewPlantVessel.id == vessel_id, BrewPlantVessel.plant_id == plant_id,
                      BrewPlantVessel.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if not vessel:
        return _workspace_form_error("Tanque desta planta não encontrado.", 404, plant_id=plant_id, tab="plant")
    label = (request.form.get("label_text") or "").strip()
    kind = request.form.get("vessel_type")
    order = request.form.get("position_order", type=int)
    if not label or len(label) > 100 or kind not in ("mash_tun", "boil_kettle", "hlt", "fermenter", "bright_tank") or order is None or order < 0:
        return _workspace_form_error("Informe identificação, tipo e ordem válidos.", 400, plant_id=plant_id, tab="plant")
    result = BrewPlantVesselService().update(vessel_id, {"label_text": label, "vessel_type": kind,
        "position_order": order, "description": (request.form.get("description") or "").strip()})
    return _workspace_form_result(result, plant_id=plant_id, tab="plant", status=200)


def _workspace_form_error(message: str, code: int, *, plant_id: int, tab: str):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": False, "error": message}), code
    flash(message, "error")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab=tab))


@plant_workspace_bp.route("/<int:plant_id>/vessels", methods=["POST"])
@login_required
@permission_required("brew_plant_vessels.create")
def create_vessel(plant_id: int):
    plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False, is_active=True).first()
    if not plant:
        return _workspace_form_error("Planta ativa não encontrada.", 404, plant_id=plant_id, tab="plant")
    label = (request.form.get("label_text") or "").strip()
    vessel_type = request.form.get("vessel_type") or ""
    allowed = ("mash_tun", "boil_kettle", "hlt", "fermenter", "bright_tank")
    if not label or len(label) > 100 or vessel_type not in allowed:
        return _workspace_form_error("Informe nome e tipo válidos para o tanque.", 400, plant_id=plant_id, tab="plant")
    result = BrewPlantVesselService().create({"plant_id": plant_id, "label_text": label,
                                              "vessel_type": vessel_type})
    return _workspace_form_result(result, plant_id=plant_id, tab="plant")


@plant_workspace_bp.route("/<int:plant_id>/mappings", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.create")
def create_mapping(plant_id: int):
    return _save_mapping(plant_id)


@plant_workspace_bp.route("/<int:plant_id>/mappings/<int:mapping_id>/edit", methods=["POST"])
@login_required
@permission_required("brew_plant_mappings.update")
def update_mapping(plant_id, mapping_id):
    mapping = (BrewPlantMapping.query.join(BrewPlantVessel)
               .filter(BrewPlantMapping.id == mapping_id, BrewPlantMapping.is_deleted.is_(False),
                       BrewPlantVessel.plant_id == plant_id, BrewPlantVessel.is_deleted.is_(False)).first())
    if not mapping:
        return _workspace_form_error("Mapeamento desta planta não encontrado.", 404, plant_id=plant_id, tab="plant")
    return _save_mapping(plant_id, mapping)


def _save_mapping(plant_id, mapping=None):
    plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first()
    if plant and mapping is None and not plant.is_active:
        plant = None
    if not plant:
        return _workspace_form_error("Planta ativa não encontrada.", 404, plant_id=plant_id, tab="plant")
    vessel_id = request.form.get("vessel_id", type=int)
    vessel = BrewPlantVessel.query.filter_by(id=vessel_id, plant_id=plant_id, is_deleted=False).first()
    if not vessel:
        return _workspace_form_error("Selecione um tanque desta planta.", 400, plant_id=plant_id, tab="plant")
    role_key = (request.form.get("role_key") or "").strip()
    category_for_role = {"sensor_temp": "sensor", "actor_heat": "actuator", "actor_flow": "actuator"}
    preserve_custom_role = mapping is not None and role_key == mapping.role_key and role_key not in category_for_role
    if role_key not in category_for_role and not preserve_custom_role:
        return _workspace_form_error("Selecione um papel válido.", 400, plant_id=plant_id, tab="plant")
    function_name = (request.form.get("device_function_name") or "").strip()
    function = get_function_by_name(function_name)
    if not function or (not preserve_custom_role and function.get("category") not in (category_for_role[role_key], "hybrid")):
        return _workspace_form_error("Selecione uma função compatível com o papel.", 400, plant_id=plant_id, tab="plant")
    duplicate = BrewPlantMapping.query.filter_by(vessel_id=vessel_id, role_key=role_key, is_deleted=False)
    if mapping is not None:
        duplicate = duplicate.filter(BrewPlantMapping.id != mapping.id)
    if duplicate.first():
        return _workspace_form_error("Este tanque já possui um mapeamento para esse papel.", 409, plant_id=plant_id, tab="plant")
    data = {
        "vessel_id": vessel_id, "role_key": role_key,
        "device_function_name": function_name,
        "is_required": request.form.get("is_required") == "on",
    }
    label_text = (request.form.get("label_text") or "").strip()
    if len(label_text) > 100:
        return _workspace_form_error("A identificação do vínculo deve ter até 100 caracteres.", 400, plant_id=plant_id, tab="plant")
    if mapping is not None:
        data["label_text"] = label_text
        result = BrewPlantMappingService().update(mapping.id, data)
    else:
        result = BrewPlantMappingService().create(data)
    return _workspace_form_result(result, plant_id=plant_id, tab="plant", status=200 if mapping is not None else 201)


@plant_workspace_bp.route("/<int:plant_id>/dashboard-layouts", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.create")
def create_layout(plant_id: int):
    plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False, is_active=True).first()
    if not plant:
        return _workspace_form_error("Planta ativa não encontrada.", 404, plant_id=plant_id, tab="dashboard")
    name = (request.form.get("name") or "").strip()
    if not name or len(name) > 100:
        return _workspace_form_error("Informe um nome de layout com até 100 caracteres.", 400, plant_id=plant_id, tab="dashboard")
    first_layout = DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False).first() is None
    result = DashboardLayoutService().create({"plant_id": plant_id, "name": name,
                                              "is_default": first_layout})
    return _workspace_form_result(result, plant_id=plant_id, tab="dashboard")


@plant_workspace_bp.route("/<int:plant_id>/dashboard-layouts/<int:layout_id>/edit", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def update_layout(plant_id, layout_id):
    layout = (DashboardLayout.query.join(BrewPlant)
              .filter(DashboardLayout.id == layout_id, DashboardLayout.plant_id == plant_id,
                      DashboardLayout.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if not layout:
        return _workspace_form_error("Layout desta planta não encontrado.", 404, plant_id=plant_id, tab="dashboard")
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    width = request.form.get("canvas_width", type=int)
    height = request.form.get("canvas_height", type=int)
    if not name or len(name) > 100 or len(description) > 500:
        return _workspace_form_error("Informe nome com até 100 e descrição com até 500 caracteres.", 400, plant_id=plant_id, tab="dashboard")
    if width is None or height is None or width <= 0 or height <= 0:
        return _workspace_form_error("Informe largura e altura inteiras e positivas.", 400, plant_id=plant_id, tab="dashboard")
    result = DashboardLayoutService().update(layout_id, {"name": name, "description": description,
                                            "canvas_width": width, "canvas_height": height})
    return _workspace_form_result(result, plant_id=plant_id, tab="dashboard", status=200)


@plant_workspace_bp.route("/<int:plant_id>", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def shell(plant_id: int):
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        flash("Planta não encontrada.", "error")
        return redirect(url_for("plant_workspace.landing"))
    initial_tab = request.args.get("tab", "dashboard")
    if initial_tab not in {tab["key"] for tab in _TABS}:
        initial_tab = "dashboard"
    return render_template("plant_workspace/shell.html", plant=plant, tabs=_TABS, initial_tab=initial_tab,
                           initial_session_id=request.args.get("session_id"))


@plant_workspace_bp.route("/<int:plant_id>/tab/dashboard", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def tab_dashboard(plant_id: int):
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    layouts = DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False)
    if "layout_id" in request.args:
        layout = layouts.filter_by(id=request.args.get("layout_id", type=int)).first()
        if not layout:
            return render_template("plant_workspace/_tab_error.html", message="Layout desta planta não encontrado."), 404
    else:
        layout = (layouts.filter_by(is_default=True).first()
                  or layouts.order_by(DashboardLayout.id).first())
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


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/edit", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
def update_session(plant_id, session_id):
    session = (BrewSession.query.join(BrewPlant)
               .filter(BrewSession.id == session_id, BrewSession.plant_id == plant_id,
                       BrewSession.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if not session:
        return _workspace_form_error("Sessão desta planta não encontrada.", 404, plant_id=plant_id, tab="sessions")
    name = (request.form.get("name") or "").strip()
    if not name or len(name) > 100:
        return _workspace_form_error("Informe um nome de sessão com até 100 caracteres.", 400, plant_id=plant_id, tab="sessions")
    raw_volume = (request.form.get("volume_real_litros") or "").strip()
    try:
        import math
        volume = float(raw_volume.replace(",", ".")) if raw_volume else None
        if volume is not None and (not math.isfinite(volume) or volume < 0):
            raise ValueError
    except ValueError:
        return _workspace_form_error("Informe volume real não negativo ou deixe em branco.", 400, plant_id=plant_id, tab="sessions")
    result = BrewSessionService().update(session_id, {"name": name,
        "notes": request.form.get("notes", ""), "volume_real_litros": volume})
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        flash("Sessão atualizada." if result.success else result.error, "success" if result.success else "error")
        return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="sessions", session_id=session_id))
    return _workspace_form_result(result, plant_id=plant_id, tab="sessions", status=200)


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/confirm-ingredients", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
def confirm_session_ingredients(plant_id, session_id):
    session = (BrewSession.query.join(BrewPlant)
               .filter(BrewSession.id == session_id, BrewSession.plant_id == plant_id,
                       BrewSession.is_deleted.is_(False), BrewPlant.is_deleted.is_(False)).first())
    if not session:
        return _workspace_form_error("Sessão desta planta não encontrada.", 404, plant_id=plant_id, tab="sessions")
    try:
        result = ingredient_consumption_service.confirmar_consumo_ingredientes(session_id)
    except ingredient_consumption_service.LoteNaoEncontradoError:
        return _workspace_form_error("Sessão não encontrada.", 404, plant_id=plant_id, tab="sessions")
    except ingredient_consumption_service.ReceitaNaoVinculadaError:
        return _workspace_form_error("Vincule uma receita antes de confirmar ingredientes.", 400, plant_id=plant_id, tab="sessions")
    except ValueError as exc:
        return _workspace_form_error(str(exc), 400, plant_id=plant_id, tab="sessions")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha na confirmação dos ingredientes da sessão %s", session_id)
        return _workspace_form_error("Não foi possível confirmar os ingredientes. Nenhuma baixa foi confirmada.", 500, plant_id=plant_id, tab="sessions")
    message = "Ingredientes já estavam confirmados." if result["ja_confirmado"] else "Ingredientes confirmados."
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "id": session_id, "message": message,
                        "ja_confirmado": result["ja_confirmado"],
                        "custo_total_insumos": result["custo_total_insumos"]})
    flash(message, "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="sessions", session_id=session_id))


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/alarms/<int:alarm_id>/acknowledge", methods=["POST"])
@login_required
@permission_required("brew_session_alarms.update")
def acknowledge_session_alarm(plant_id, session_id, alarm_id):
    try:
        result = acknowledge_alarm(plant_id, session_id, alarm_id, int(current_user.id))
    except SessionAlarmNotFound as exc:
        return _workspace_form_error(str(exc), 404, plant_id=plant_id, tab="sessions")
    except Exception:
        current_app.logger.exception("Falha ao reconhecer alarme %s da sessão %s", alarm_id, session_id)
        return _workspace_form_error("Não foi possível registrar o reconhecimento do alarme.", 500, plant_id=plant_id, tab="sessions")
    message = "Alarme já estava reconhecido." if result["ja_reconhecido"] else "Alarme reconhecido."
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "id": alarm_id, "message": message, **result})
    flash(message, "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="sessions", session_id=session_id))


@plant_workspace_bp.route("/<int:plant_id>/tab/sessions", methods=["GET"])
@login_required
@permission_required("brew_sessions.list")
def tab_sessions(plant_id: int):
    """Aba Sessões (conversa): consolida Sessões de Brassagem + Passos
    da Sessão (visão ENXUTA, só acompanhamento — não é o CRUD completo
    de `brew_session_steps`, de propósito) + Logs + Alarmes recentes.

    "Adicionar Etapa" usa a aba Receita Mash para alterar a receita-modelo.
    "Nova" abre o seletor de receitas da mesma aba."""
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    search = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    alarm_state = (request.args.get("alarm_state") or "").strip()
    if alarm_state not in ("", "pending", "acknowledged"):
        return render_template("plant_workspace/_tab_error.html", message="Filtro de alarmes inválido."), 400
    if status_filter not in ("", "draft", "active", "paused", "completed", "aborted"):
        return render_template("plant_workspace/_tab_error.html", message="Status de sessão inválido."), 400
    base_query = BrewSession.query.filter_by(plant_id=plant_id, is_deleted=False)
    sessions_query = base_query
    if search:
        sessions_query = sessions_query.filter(BrewSession.name.contains(search, autoescape=True))
    if status_filter:
        sessions_query = sessions_query.filter_by(status=status_filter)

    def page_items(query, key):
        page = max(1, request.args.get(key, 1, type=int) or 1)
        rows = query.offset((page - 1) * 20).limit(21).all()
        return rows[:20], {"page": page, "has_next": len(rows) > 20}

    sessions, session_page = page_items(sessions_query.order_by(BrewSession.id.desc()), "page")
    selected_session = None
    if "session_id" in request.args:
        selected_session = base_query.filter_by(id=request.args.get("session_id", type=int)).first()
        if not selected_session:
            return render_template("plant_workspace/_tab_error.html", message="Sessão desta planta não encontrada."), 404
    elif sessions:
        selected_session = (
            next((s for s in sessions if s.status == "active"), None) or sessions[0]
        )

    steps, logs, alarms = [], [], []
    conference, estimated_cost = None, None
    envases = []
    pending_alarm_count = 0
    log_page = {"page": 1, "has_next": False}
    alarm_page = {"page": 1, "has_next": False}
    if selected_session:
        if selected_session.recipe_id and selected_session.insumos_baixados_em is None:
            conference = conferir_ingredientes(selected_session.recipe_id)
            estimated_cost = calcular_custo_insumos_receita(selected_session.recipe_id)
        if current_user.has_permission("envases.list"):
            envases = (Envase.query.filter_by(lote_id=selected_session.id, is_deleted=False)
                       .order_by(Envase.id.desc()).all())
        steps = (
            BrewSessionStep.query.filter_by(session_id=selected_session.id, is_deleted=False)
            .order_by(BrewSessionStep.step_index)
            .all()
        )
        logs, log_page = page_items(
            BrewSessionLog.query.filter_by(session_id=selected_session.id, is_deleted=False)
            .order_by(BrewSessionLog.created_at.desc(), BrewSessionLog.id.desc()), "logs_page")
        alarm_query = BrewSessionAlarm.query.filter_by(session_id=selected_session.id, is_deleted=False)
        pending_alarm_count = alarm_query.filter_by(is_acknowledged=False).count()
        if alarm_state:
            alarm_query = alarm_query.filter_by(is_acknowledged=alarm_state == "acknowledged")
        alarms, alarm_page = page_items(alarm_query.order_by(BrewSessionAlarm.created_at.desc(), BrewSessionAlarm.id.desc()), "alarms_page")

    navigation = {"q": search, "status": status_filter, "page": session_page["page"],
                  "logs_page": log_page["page"], "alarms_page": alarm_page["page"], "alarm_state": alarm_state}
    if selected_session:
        navigation["session_id"] = selected_session.id

    def tab_url(**changes):
        return url_for("plant_workspace.tab_sessions", plant_id=plant_id, **{**navigation, **changes})

    for pager, key in ((session_page, "page"), (log_page, "logs_page"), (alarm_page, "alarms_page")):
        reset = {"session_id": None, "logs_page": 1, "alarms_page": 1} if key == "page" else {}
        pager["previous_url"] = tab_url(**{**reset, key: pager["page"] - 1}) if pager["page"] > 1 else None
        pager["next_url"] = tab_url(**{**reset, key: pager["page"] + 1}) if pager["has_next"] else None

    return render_template(
        "plant_workspace/_tab_sessions.html",
        plant=plant, sessions=sessions, selected_session=selected_session,
        steps=steps, logs=logs, alarms=alarms,
        search=search, status_filter=status_filter, session_page=session_page,
        log_page=log_page, alarm_page=alarm_page,
        session_urls={s.id: tab_url(session_id=s.id, logs_page=1, alarms_page=1) for s in sessions},
        conference=conference, estimated_cost=estimated_cost, envases=envases,
        alarm_state=alarm_state, pending_alarm_count=pending_alarm_count,
        alarm_filter_url=tab_url(alarms_page=1),
    )


@plant_workspace_bp.route("/<int:plant_id>/tab/plant", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def tab_plant(plant_id: int):
    """Consulta, cadastro e edição local de planta, tanques e vínculos.
    Configuração avançada e manutenção continuam nos cadastros completos."""
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
        device_functions=list_functions_for_mapping(),
    )


@plant_workspace_bp.route("/<int:plant_id>/tab/recipe", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def tab_recipe(plant_id: int):
    """Aba Receita Mash (conversa): sem `?recipe_id=`, mostra a lista
    de receitas ativas pra escolher. Com `?recipe_id=`, reúne ficha,
    ingredientes, custo e timeline da receita; o formulário gera a
    sessão e seleciona o novo lote na aba Sessões."""
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    recipe_id = request.args.get("recipe_id", type=int)
    if recipe_id:
        recipe = MashRecipe.query.get(recipe_id)
        if not recipe or recipe.is_deleted:
            return render_template("plant_workspace/_tab_error.html", message="Receita não encontrada.")
        context = _build_recipe_view_context(recipe, is_fragment=True, default_plant_id=plant_id)
        ingredientes = RecipeIngredient.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(RecipeIngredient.id).all()
        context.update(
            plant=plant,
            ingredientes=ingredientes,
            ingredientes_por_id={ing.id: ing for ing in ingredientes},
            fermentacao=FermentationStep.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(FermentationStep.ordem).all(),
            agua=WaterProfile.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(WaterProfile.contexto).all(),
            historico=RecipeHistory.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(RecipeHistory.alterado_em.desc()).all(),
            conferencia=conferir_ingredientes(recipe.id),
            custo=calcular_custo_insumos_receita(recipe.id),
        )
        return render_template("plant_workspace/_tab_recipe_detail.html", **context)

    recipes = MashRecipe.query.filter_by(is_deleted=False, is_active=True).order_by(MashRecipe.name).all()
    return render_template("plant_workspace/_tab_recipe_picker.html", plant=plant, recipes=recipes)


@plant_workspace_bp.route("/<int:plant_id>/tab/automation", methods=["GET"])
@login_required
@permission_required("automation_rules.list")
def tab_automation(plant_id: int):
    """Aba Automação (conversa): consolida Regras de Automação +
    Histórico de disparo. `AutomationRule` não tem `plant_id` direto
    — só `session_id` (opcional, nullable). Filtro: regra "global"
    (sem sessão vinculada, vale pra qualquer sessão desta Planta) OU
    vinculada a uma sessão desta Planta especificamente."""
    plant = BrewPlant.query.get(plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    session_ids = [
        s.id for s in BrewSession.query.filter_by(plant_id=plant_id, is_deleted=False).all()
    ]
    rules = (
        AutomationRule.query.filter(
            AutomationRule.is_deleted == False,  # noqa: E712
            db.or_(AutomationRule.session_id.is_(None), AutomationRule.session_id.in_(session_ids)),
        )
        .order_by(AutomationRule.id.desc())
        .all()
    )
    rule_ids = [r.id for r in rules]
    logs = []
    if rule_ids:
        logs = (
            AutomationRuleLog.query.filter(
                AutomationRuleLog.rule_id.in_(rule_ids), AutomationRuleLog.is_deleted == False,  # noqa: E712
            )
            .order_by(AutomationRuleLog.triggered_at.desc())
            .limit(20)
            .all()
        )
    rules_by_id = {r.id: r for r in rules}

    return render_template(
        "plant_workspace/_tab_automation.html",
        plant=plant, rules=rules, logs=logs, rules_by_id=rules_by_id,
    )
