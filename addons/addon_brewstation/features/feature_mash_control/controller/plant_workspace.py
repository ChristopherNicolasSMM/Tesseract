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

from datetime import date
from uuid import uuid4
from itsdangerous import URLSafeSerializer, BadSignature

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
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_sanitation_service
from addons.addon_brewstation.features.feature_mash_control.services import ingredient_resolution_service
from sqlalchemy.exc import IntegrityError
from addons.addon_estoque.root.services import material_lookup
from addons.addon_brewstation.features.feature_mash_control.services.session_alarm_actions import (
    acknowledge_alarm, SessionAlarmNotFound,
)
from addons.addon_brewstation.features.feature_envase.model.envase import Envase
from addons.addon_brewstation.features.feature_envase.services import envase_preparation_service, envase_estoque_service
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


@plant_workspace_bp.route("/<int:plant_id>/dashboard-layouts/<int:layout_id>/appearance", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def configure_layout_appearance(plant_id, layout_id):
    from addons.addon_brewstation.features.feature_mash_control.services.dashboard_workspace_actions import configure_layout
    try:
        layout = configure_layout(plant_id, layout_id,
            color=request.form.get("background_color"), image=request.form.get("background_image_url"),
            is_default=request.form.get("is_default") == "on")
    except LookupError as exc:
        return _workspace_form_error(str(exc), 404, plant_id=plant_id, tab="dashboard")
    except ValueError as exc:
        return _workspace_form_error(str(exc), 400, plant_id=plant_id, tab="dashboard")
    except Exception:
        current_app.logger.exception("Falha ao configurar fundo/padrão do painel %s", layout_id)
        return _workspace_form_error("Não foi possível salvar o painel. Alterações desfeitas.", 500,
                                     plant_id=plant_id, tab="dashboard")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "id": layout.id, "layout_id": layout.id, "message": "Fundo e painel padrão salvos."})
    flash("Fundo e painel padrão salvos.", "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="dashboard", layout_id=layout.id))


@plant_workspace_bp.route("/<int:plant_id>/dashboard-layouts/<int:layout_id>/trash", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.trash")
def trash_workspace_layout(plant_id, layout_id):
    return _maintain_workspace_layout(plant_id, layout_id, "trash")


@plant_workspace_bp.route("/<int:plant_id>/dashboard-layouts/<int:layout_id>/restore", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.restore")
def restore_workspace_layout(plant_id, layout_id):
    return _maintain_workspace_layout(plant_id, layout_id, "restore")


def _maintain_workspace_layout(plant_id, layout_id, action):
    from addons.addon_brewstation.features.feature_mash_control.services.dashboard_workspace_actions import maintain_layout
    try:
        selected = maintain_layout(plant_id, layout_id, action)
    except LookupError as exc:
        return _workspace_form_error(str(exc), 404, plant_id=plant_id, tab="dashboard")
    except ValueError as exc:
        return _workspace_form_error(str(exc), 400, plant_id=plant_id, tab="dashboard")
    except Exception:
        current_app.logger.exception("Falha na manutenção do painel %s (%s)", layout_id, action)
        return _workspace_form_error("Não foi possível concluir a manutenção. Alterações desfeitas.", 500,
                                     plant_id=plant_id, tab="dashboard")
    message = "Painel enviado à lixeira." if action == "trash" else "Painel restaurado."
    selected_id = selected.id if selected else None
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "dashboard_reload": True, "layout_id": selected_id, "message": message})
    flash(message, "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="dashboard", layout_id=selected_id))


@plant_workspace_bp.route("/<int:plant_id>", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def shell(plant_id: int):
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        flash("Planta não encontrada.", "error")
        return redirect(url_for("plant_workspace.landing"))
    initial_tab = request.args.get("tab", "dashboard")
    if initial_tab not in {tab["key"] for tab in _TABS}:
        initial_tab = "dashboard"
    return render_template("plant_workspace/shell.html", plant=plant, tabs=_TABS, initial_tab=initial_tab,
                           initial_session_id=request.args.get("session_id"),
                           initial_envase_id=request.args.get("envase_id"),
                           initial_recipe_id=request.args.get("recipe_id"),
                           initial_layout_id=request.args.get("layout_id"))


@plant_workspace_bp.route("/<int:plant_id>/tab/dashboard", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def tab_dashboard(plant_id: int):
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    trash_page = max(1, request.args.get("trash_page", 1, type=int) or 1)
    trash_query = DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=True)
    trash_total = trash_query.count()
    trash_pages = max(1, (trash_total + 19) // 20)
    trash_page = min(trash_page, trash_pages)
    trashed_layouts = trash_query.order_by(DashboardLayout.id.desc()).offset((trash_page - 1) * 20).limit(20).all()
    trash_context = dict(trashed_layouts=trashed_layouts, trash_total=trash_total,
                         trash_page=trash_page, trash_pages=trash_pages, plant=plant)
    layouts = DashboardLayout.query.filter_by(plant_id=plant_id, is_deleted=False)
    if "layout_id" in request.args:
        layout = layouts.filter_by(id=request.args.get("layout_id", type=int)).first()
        if not layout:
            return render_template("plant_workspace/_tab_error.html", message="Layout desta planta não encontrado."), 404
    else:
        layout = (layouts.filter_by(is_default=True).first()
                  or layouts.order_by(DashboardLayout.id).first())
    if not layout:
        return render_template("plant_workspace/_tab_dashboard_empty.html", **trash_context)

    context = _build_dashboard_view_context(layout, is_fragment=True)
    context.update(trash_context)
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
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada."), (404 if "envase_id" in request.args else 200)

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

    selected_envase = None
    if "envase_id" in request.args:
        if not (current_user.has_permission("envases.list") and current_user.has_permission("envases.detail")):
            return render_template("plant_workspace/_tab_error.html", message="Sem permissão para consultar detalhes do envase."), 403
        selected_envase = Envase.query.filter_by(
            id=request.args.get("envase_id", type=int),
            lote_id=selected_session.id if selected_session else None, is_deleted=False,
        ).first()
        if selected_envase is None:
            return render_template("plant_workspace/_tab_error.html", message="Envase deste lote não encontrado."), 404

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
        selected_envase=selected_envase,
        envase_urls={e.id: tab_url(envase_id=e.id) for e in envases},
        envase_back_url=tab_url(),
        alarm_state=alarm_state, pending_alarm_count=pending_alarm_count,
        alarm_filter_url=tab_url(alarms_page=1),
    )


@plant_workspace_bp.route("/<int:plant_id>/tab/plant", methods=["GET"])
@login_required
@permission_required("brew_plants.list")
def tab_plant(plant_id: int):
    """Consulta, cadastro e edição local de planta, tanques e vínculos.
    Configuração avançada e manutenção continuam nos cadastros completos."""
    plant = db.session.get(BrewPlant, plant_id)
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
        vessel_trash=BrewPlantVessel.query.filter_by(plant_id=plant_id, is_deleted=True).order_by(BrewPlantVessel.id).paginate(page=max(1, request.args.get("vessels_trash_page", 1, type=int) or 1), per_page=20, error_out=False),
        mapping_trash=BrewPlantMapping.query.join(BrewPlantVessel).filter(BrewPlantVessel.plant_id == plant_id, BrewPlantMapping.is_deleted.is_(True)).order_by(BrewPlantMapping.id).paginate(page=max(1, request.args.get("mappings_trash_page", 1, type=int) or 1), per_page=20, error_out=False),
    )


@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/ingredients/<int:ingredient_id>/sanitize", methods=["POST"])
@login_required
@permission_required("recipe_ingredients.update")
def sanitize_recipe_ingredient(plant_id, recipe_id, ingredient_id):
    def respond(message, code=200):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": code == 200, "message" if code == 200 else "error": message}), code
        flash(message, "success" if code == 200 else "error")
        return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="recipe", recipe_id=recipe_id))

    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return respond("Planta não encontrada.", 404)
    try:
        raw_material = (request.form.get("material_id") or "").strip()
        try:
            material_id = int(raw_material) if raw_material else None
        except ValueError:
            return respond("Selecione um Material de Estoque válido.", 400)
        ingredient_sanitation_service.sanear_ingrediente(
            recipe_id, ingredient_id, material_id=material_id,
            status_resolucao=request.form.get("status_resolucao", ""),
        )
    except ingredient_sanitation_service.IngredienteNaoEncontradoError as exc:
        return respond(str(exc), 404)
    except ingredient_sanitation_service.ReceitaEmUsoError as exc:
        return respond(str(exc), 409)
    except ValueError as exc:
        return respond(str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao sanear ingrediente %s da receita %s", ingredient_id, recipe_id)
        return respond("Não foi possível salvar o vínculo. Nenhuma alteração foi confirmada.", 500)
    return respond("Decisão do ingrediente salva. Confira as pendências e o custo estimado; o estoque não foi movimentado.")


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/envases/<int:envase_id>/reverse", methods=["POST"])
@login_required
@permission_required("brew_sessions.list")
@permission_required("envases.list")
@permission_required("envases.detail")
@permission_required("envases.update")
def reverse_session_envase(plant_id, session_id, envase_id):
    plant = BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first()
    session = BrewSession.query.filter_by(id=session_id, plant_id=plant_id, is_deleted=False).first()
    envase = Envase.query.filter_by(id=envase_id, lote_id=session_id, is_deleted=False).first()
    if plant is None or session is None or envase is None:
        return jsonify(ok=False, error="Envase deste lote e planta não encontrado."), 404
    motivo = request.form.get("motivo", "").strip()
    if not motivo or len(motivo) > 1000:
        return jsonify(ok=False, error="Informe o motivo do estorno com até 1000 caracteres."), 400
    try:
        envase_estoque_service.estornar_envase(envase_id, motivo, usuario_id=current_user.id)
    except envase_estoque_service.EnvaseNaoEstornavelError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Falha ao estornar envase %s do lote %s", envase_id, session_id)
        return jsonify(ok=False, error="Não foi possível estornar o envase. Nenhuma devolução desta tentativa foi mantida."), 500
    return jsonify(ok=True, message="Envase cancelado e embalagens devolvidas ao estoque.",
                   reload_url=url_for("plant_workspace.tab_sessions", plant_id=plant_id,
                                      session_id=session_id, envase_id=envase_id))


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/prepare-envase", methods=["GET"])
@login_required
@permission_required("brew_sessions.list")
@permission_required("envases.list")
@permission_required("envases.create")
def prepare_session_envase(plant_id, session_id):
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return jsonify(ok=False, error="Planta não encontrada."), 404
    session = BrewSession.query.filter_by(id=session_id, plant_id=plant_id, is_deleted=False).first()
    if session is None:
        return jsonify(ok=False, error="Sessão desta planta não encontrada."), 404
    try:
        material_id = int(request.args.get("material_resultante_id", ""))
        liters = float(request.args.get("quantidade_litros", "").replace(",", "."))
    except ValueError:
        return jsonify(ok=False, error="Selecione o material resultante e informe os litros válidos."), 400
    try:
        preview = envase_preparation_service.preparar_envase(session_id, material_id, liters)
        data_envase = request.args.get("data_envase") or None
        if data_envase:
            date.fromisoformat(data_envase)
        tipo_envase = (request.args.get("tipo_envase") or "").strip() or None
        if tipo_envase and len(tipo_envase) > 30:
            raise ValueError("Tipo de envase deve ter até 30 caracteres.")
        token = _envase_confirmation_signer().dumps({
            "plant_id": plant_id, "session_id": session_id, "material_id": material_id,
            "liters": liters, "data_envase": data_envase, "tipo_envase": tipo_envase,
            "key": uuid4().hex,
        })
        can_register = (preview["insumos_confirmados"] or
                        bool(session.recipe_id) and not preview["pendencias_ingredientes"])
        if not preview["insumos_confirmados"] and not current_user.has_permission("brew_sessions.update"):
            can_register = False
        html = render_template("plant_workspace/_envase_preview.html", preview=preview,
                               token=token, can_register=can_register,
                               register_url=url_for("plant_workspace.register_session_envase",
                                                    plant_id=plant_id, session_id=session_id))
    except envase_preparation_service.PreparacaoNaoEncontradaError as exc:
        return jsonify(ok=False, error=str(exc)), 404
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Falha na prévia de envase do lote %s", session_id)
        return jsonify(ok=False, error="Não foi possível preparar a prévia de envase."), 500
    return jsonify(ok=True, html=html)


def _envase_confirmation_signer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="workspace-envase-confirmation-v1")


@plant_workspace_bp.route("/<int:plant_id>/sessions/<int:session_id>/register-envase", methods=["POST"])
@login_required
@permission_required("brew_sessions.list")
@permission_required("envases.list")
@permission_required("envases.create")
def register_session_envase(plant_id, session_id):
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return jsonify(ok=False, error="Planta não encontrada."), 404
    session = BrewSession.query.filter_by(id=session_id, plant_id=plant_id, is_deleted=False).first()
    if session is None:
        return jsonify(ok=False, error="Sessão desta planta não encontrada."), 404
    try:
        payload = _envase_confirmation_signer().loads(request.form.get("confirmation_token", ""))
    except BadSignature:
        return jsonify(ok=False, error="Confirmação inválida. Consulte novamente a prévia."), 400
    if payload.get("plant_id") != plant_id or payload.get("session_id") != session_id:
        return jsonify(ok=False, error="A confirmação pertence a outro contexto."), 400
    if session.insumos_baixados_em is None and not current_user.has_permission("brew_sessions.update"):
        return jsonify(ok=False, error="É necessária permissão para confirmar os ingredientes deste lote."), 403
    try:
        result = envase_estoque_service.registrar_envase(
            session_id, payload["material_id"], payload["liters"],
            data_envase=date.fromisoformat(payload["data_envase"]) if payload["data_envase"] else None,
            tipo_envase=payload["tipo_envase"], idempotency_key=payload["key"],
            usuario_id=current_user.id,
        )
    except (ValueError, envase_estoque_service.LoteNaoEncontradoError,
            envase_estoque_service.MaterialNaoEncontradoError,
            envase_estoque_service.VolumeRealNaoConfiguradoError,
            ingredient_consumption_service.ReceitaNaoVinculadaError,
            ingredient_consumption_service.IngredientesPendentesError) as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao registrar envase do lote %s", session_id)
        return jsonify(ok=False, error="O envase não foi confirmado. Nenhuma movimentação desta tentativa foi mantida."), 500
    return jsonify(ok=True, envase_id=result["envase"]["id"], ja_registrado=result["ja_registrado"],
                   message="Esta confirmação já foi registrada; nenhuma baixa adicional foi feita."
                           if result["ja_registrado"] else "Envase registrado com sucesso.",
                   url=url_for("plant_workspace.tab_sessions", plant_id=plant_id, session_id=session_id))


def _recipe_workspace_response(plant_id, selected_recipe_id, message, code=200, **extra):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": code == 200, "message" if code == 200 else "error": message, **extra}), code
    flash(message, "success" if code == 200 else "error")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="recipe", recipe_id=selected_recipe_id))


@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/revise", methods=["POST"])
@login_required
@permission_required("mash_recipes.create")
@permission_required("recipe_steps.list")
def revise_recipe(plant_id, recipe_id):
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return _recipe_workspace_response(plant_id, recipe_id, "Planta não encontrada.", 404)
    try:
        result = ingredient_resolution_service.criar_nova_versao(
            recipe_id, {}, usuario_id=current_user.id,
            observacao=(request.form.get("observacao") or "Revisão criada no workspace da planta."),
        )
    except ingredient_resolution_service.ReceitaNaoEncontradaError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 404)
    except IntegrityError:
        db.session.rollback()
        return _recipe_workspace_response(plant_id, recipe_id, "Houve conflito ao criar a versão. Atualize a receita e tente novamente.", 409)
    except ValueError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao revisar receita %s", recipe_id)
        return _recipe_workspace_response(plant_id, recipe_id, "Não foi possível criar a revisão. Nenhuma cópia parcial foi confirmada.", 500)
    new_id = result["recipe"]["id"]
    return _recipe_workspace_response(plant_id, new_id, f"Revisão v{result['recipe']['versao']} criada. Os lotes anteriores mantêm a receita original.",
                                      recipe_id=new_id)


@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/ingredients/<int:ingredient_id>/edit-data", methods=["POST"])
@login_required
@permission_required("recipe_ingredients.update")
def edit_recipe_ingredient_data(plant_id, recipe_id, ingredient_id):
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return _recipe_workspace_response(plant_id, recipe_id, "Planta não encontrada.", 404)
    try:
        dados = {field: request.form[field] for field in ingredient_sanitation_service.INGREDIENT_DATA_FIELDS if field in request.form}
        ingredient_sanitation_service.editar_dados_ingrediente(
            recipe_id, ingredient_id, dados, usuario_id=current_user.id,
        )
    except ingredient_sanitation_service.IngredienteNaoEncontradoError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 404)
    except ingredient_sanitation_service.ReceitaEmUsoError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 409)
    except ValueError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao editar dados do ingrediente %s", ingredient_id)
        return _recipe_workspace_response(plant_id, recipe_id, "Não foi possível salvar os dados. Nenhuma alteração parcial foi confirmada.", 500)
    return _recipe_workspace_response(plant_id, recipe_id, "Dados salvos. Confira as pendências, alertas e o custo estimado; o estoque não foi movimentado.")


@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/ingredients/<int:ingredient_id>/conversion", methods=["POST"])
@login_required
@permission_required("recipe_steps.list")
@permission_required("material_unidades.create")
def configure_recipe_ingredient_conversion(plant_id, recipe_id, ingredient_id):
    from services.core.i18n_service import translate as t
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.conversion.plant_missing"), 404)
    try:
        ingredient_sanitation_service.configure_ingredient_conversion(
            recipe_id, ingredient_id,
            material_id_esperado=request.form.get("material_id", type=int),
            unidade_base_esperada=request.form.get("unidade_base", ""),
            unidade_origem_esperada=request.form.get("unidade_origem", ""),
            fator=request.form.get("fator_para_base"),
        )
    except ingredient_sanitation_service.IngredienteNaoEncontradoError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 404)
    except ValueError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao cadastrar conversão do ingrediente %s", ingredient_id)
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.conversion.failed"), 500)
    return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.conversion.saved"))


@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/preparation/<kind>/<action>", defaults={"row_id": None}, methods=["POST"])
@plant_workspace_bp.route("/<int:plant_id>/recipes/<int:recipe_id>/preparation/<kind>/<int:row_id>/<action>", methods=["POST"])
@login_required
@permission_required("recipe_steps.list")
def prepare_workspace_recipe(plant_id, recipe_id, kind, action, row_id):
    from services.core.i18n_service import translate as t
    from addons.addon_brewstation.features.feature_mash_control.services import workspace_recipe_preparation as preparation
    if kind not in preparation.FIELDS or action not in ("save", "trash", "restore"):
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.preparation.invalid_action"), 400)
    plural = {"recipe": "mash_recipes", "fermentation": "fermentation_steps", "water": "water_profiles"}[kind]
    permission = "update" if kind == "recipe" or row_id else "create"
    if action != "save": permission = action
    if not current_user.has_permission(plural + "." + permission):
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.preparation.forbidden"), 403)
    if not BrewPlant.query.filter_by(id=plant_id, is_deleted=False).first():
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.conversion.plant_missing"), 404)
    try:
        preparation.save_preparation(recipe_id, kind, action,
            {field: request.form.get(field) for field in preparation.FIELDS[kind]} if action == "save" else {},
            row_id=row_id, user_id=current_user.id)
    except preparation.PreparationNotFound as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 404)
    except preparation.PreparationConflict as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 409)
    except ValueError as exc:
        return _recipe_workspace_response(plant_id, recipe_id, str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha na preparação da receita %s", recipe_id)
        return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.preparation.failed"), 500)
    return _recipe_workspace_response(plant_id, recipe_id, t("brewstation_mashctrl.preparation.saved"), recipe_id=recipe_id)


@plant_workspace_bp.route("/<int:plant_id>/maintenance/<kind>/<int:record_id>/<action>", methods=["POST"])
@login_required
@permission_required("brew_plants.list")
def maintain_workspace_configuration(plant_id, kind, record_id, action):
    from services.core.i18n_service import translate as t
    from addons.addon_brewstation.features.feature_mash_control.services import workspace_plant_maintenance as maintenance
    if kind not in ("vessels", "mappings") or action not in ("trash", "restore"):
        return _workspace_form_error(t("brewstation_mashctrl.maintenance.invalid_action"), 400, plant_id=plant_id, tab="plant")
    plural = "brew_plant_vessels" if kind == "vessels" else "brew_plant_mappings"
    if not current_user.has_permission(plural + "." + action):
        return _workspace_form_error(t("brewstation_mashctrl.preparation.forbidden"), 403, plant_id=plant_id, tab="plant")
    try:
        maintenance.maintain(plant_id, kind, record_id, action)
    except maintenance.MaintenanceNotFound as exc:
        return _workspace_form_error(str(exc), 404, plant_id=plant_id, tab="plant")
    except maintenance.MaintenanceConflict as exc:
        return _workspace_form_error(str(exc), 409, plant_id=plant_id, tab="plant")
    except ValueError as exc:
        return _workspace_form_error(str(exc), 400, plant_id=plant_id, tab="plant")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha na manutenção %s/%s", kind, record_id)
        return _workspace_form_error(t("brewstation_mashctrl.preparation.failed"), 500, plant_id=plant_id, tab="plant")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(ok=True, message=t("brewstation_mashctrl.maintenance.saved"))
    flash(t("brewstation_mashctrl.maintenance.saved"), "success")
    return redirect(url_for("plant_workspace.shell", plant_id=plant_id, tab="plant"))


@plant_workspace_bp.route("/<int:plant_id>/tab/recipe", methods=["GET"])
@login_required
@permission_required("recipe_steps.list")
def tab_recipe(plant_id: int):
    """Aba Receita Mash (conversa): sem `?recipe_id=`, mostra a lista
    de receitas ativas pra escolher. Com `?recipe_id=`, reúne ficha,
    ingredientes, custo e timeline da receita; o formulário gera a
    sessão e seleciona o novo lote na aba Sessões."""
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada."), 404

    recipe_id = request.args.get("recipe_id", type=int)
    if "recipe_id" in request.args:
        if recipe_id is None or recipe_id <= 0:
            return render_template("plant_workspace/_tab_error.html", message="Receita não encontrada."), 404
        recipe = db.session.get(MashRecipe, recipe_id)
        if not recipe or recipe.is_deleted:
            return render_template("plant_workspace/_tab_error.html", message="Receita não encontrada."), 404
        context = _build_recipe_view_context(recipe, is_fragment=True, default_plant_id=plant_id)
        ingredientes = RecipeIngredient.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(RecipeIngredient.id).all()
        context.update(
            plant=plant,
            receita_em_uso=BrewSession.query.filter_by(recipe_id=recipe.id).first() is not None,
            pode_sanear=current_user.has_permission("recipe_ingredients.update"),
            pode_revisar=current_user.has_permission("mash_recipes.create"),
            pode_configurar_conversao=current_user.has_permission("material_unidades.create"),
            conversoes={ing.id: ingredient_sanitation_service.ingredient_conversion_context(ing) for ing in ingredientes},
            materiais_vinculados={mid: material_lookup.get_material(mid) for mid in {ing.material_id for ing in ingredientes if ing.material_id}},
            ingredientes=ingredientes,
            ingredientes_por_id={ing.id: ing for ing in ingredientes},
            fermentacao=FermentationStep.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(FermentationStep.ordem).all(),
            agua=WaterProfile.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(WaterProfile.contexto).all(),
            historico=RecipeHistory.query.filter_by(recipe_id=recipe.id, is_deleted=False).order_by(RecipeHistory.alterado_em.desc()).all(),
            fermentation_trash=FermentationStep.query.filter_by(recipe_id=recipe.id, is_deleted=True).order_by(FermentationStep.ordem).all(),
            water_trash=WaterProfile.query.filter_by(recipe_id=recipe.id, is_deleted=True).all(),
            recipe_versions=MashRecipe.query.filter_by(origem_receita=recipe.origem_receita, origem_receita_id=recipe.origem_receita_id, is_deleted=False).order_by(MashRecipe.versao.desc(), MashRecipe.id.desc()).all() if recipe.origem_receita_id else MashRecipe.query.filter_by(name=recipe.name, is_deleted=False).order_by(MashRecipe.versao.desc()).all(),
            conferencia=conferir_ingredientes(recipe.id),
            custo=calcular_custo_insumos_receita(recipe.id),
        )
        return render_template("plant_workspace/_tab_recipe_detail.html", **context)

    recipes = MashRecipe.query.filter_by(is_deleted=False, is_active=True).order_by(MashRecipe.name).all()
    return render_template("plant_workspace/_tab_recipe_picker.html", plant=plant, recipes=recipes)


@plant_workspace_bp.route("/<int:plant_id>/receitas/<int:recipe_id>/estoque-organizacional", methods=["GET"])
@login_required
@permission_required('recipe_steps.list')
@permission_required('saldos.list')
def recipe_organization_preview(plant_id, recipe_id):
    from services.core.organization_service import list_organizations
    from addons.addon_brewstation.features.feature_mash_control.services.organization_recipe_preview import preview
    plant = db.session.get(BrewPlant, plant_id)
    recipe = db.session.get(MashRecipe, recipe_id)
    if not plant or plant.is_deleted or not recipe or recipe.is_deleted:
        return jsonify(success=False, error='Planta ou receita não encontrada.'), 404
    code = request.args.get('organization_code')
    result, error, status = None, None, 200
    if code is not None:
        try:
            result = preview(recipe_id, code)
        except ValueError as exc:
            error, status = str(exc), 422
    if request.args.get('format') == 'json':
        if code is None:
            return jsonify(success=False, error='Selecione explicitamente uma organização.'), 422
        return jsonify(success=error is None, data=result, error=error), status
    organizations = [{'code': org.code, 'name': org.name} for org in list_organizations() if org.is_active]
    return render_template('plant_workspace/organization_recipe_preview.html', plant=plant,
        recipe=recipe, organizations=organizations, selected=code, result=result, error=error), status


@plant_workspace_bp.route("/<int:plant_id>/tab/automation", methods=["GET"])
@login_required
@permission_required("automation_rules.list")
def tab_automation(plant_id: int):
    """Consulta contextual; o vínculo da regra não muda o motor de execução."""
    plant = db.session.get(BrewPlant, plant_id)
    if not plant or plant.is_deleted:
        return render_template("plant_workspace/_tab_error.html", message="Planta não encontrada.")

    search = request.args.get("q", "").strip()
    active = request.args.get("active", "")
    scope = request.args.get("scope", "")
    outcome = request.args.get("outcome", "")
    if active not in ("", "active", "inactive") or scope not in ("", "global", "session") or outcome not in ("", "success", "error"):
        return render_template("plant_workspace/_tab_error.html", message="Filtro de automação inválido."), 400
    session_ids = BrewSession.query.with_entities(BrewSession.id).filter_by(plant_id=plant_id, is_deleted=False)
    base = AutomationRule.query.filter(
        AutomationRule.is_deleted.is_(False),
        db.or_(AutomationRule.session_id.is_(None), AutomationRule.session_id.in_(session_ids)),
    )
    selected_rule = None
    raw_rule_id = request.args.get("rule_id", "")
    if raw_rule_id:
        try:
            selected_rule = base.filter(AutomationRule.id == int(raw_rule_id)).first()
        except ValueError:
            pass
        if selected_rule is None:
            return render_template("plant_workspace/_tab_error.html", message="Regra não encontrada nesta planta."), 404
    filtered = base
    if search:
        filtered = filtered.filter(AutomationRule.name.contains(search, autoescape=True))
    if active:
        filtered = filtered.filter(AutomationRule.is_active.is_(active == "active"))
    if scope:
        filtered = filtered.filter(AutomationRule.session_id.is_(None) if scope == "global" else AutomationRule.session_id.is_not(None))
    if selected_rule:
        filtered = filtered.filter(AutomationRule.id == selected_rule.id)

    def paginate(query, argument):
        total = query.count()
        pages = max(1, (total + 19) // 20)
        page = min(max(1, request.args.get(argument, 1, type=int)), pages)
        return query.offset((page - 1) * 20).limit(20).all(), page, pages, total

    rules, rules_page, rules_pages, rules_total = paginate(filtered.order_by(AutomationRule.id.desc()), "rules_page")
    can_view_logs = current_user.has_permission("automation_rule_logs.list")
    logs, logs_page, logs_pages, logs_total = [], 1, 1, 0
    if can_view_logs:
        log_query = AutomationRuleLog.query.filter(
            AutomationRuleLog.is_deleted.is_(False),
            AutomationRuleLog.rule_id.in_(filtered.with_entities(AutomationRule.id)),
        )
        if outcome:
            log_query = log_query.filter(AutomationRuleLog.success.is_(outcome == "success"))
        logs, logs_page, logs_pages, logs_total = paginate(
            log_query.order_by(AutomationRuleLog.triggered_at.desc(), AutomationRuleLog.id.desc()), "logs_page")
    rules_by_id = {rule.id: rule for rule in rules}
    if logs:
        rules_by_id.update({rule.id: rule for rule in base.filter(AutomationRule.id.in_([log.rule_id for log in logs])).all()})
    can_restore = current_user.has_permission("automation_rules.restore")
    trash_query = AutomationRule.query.filter(AutomationRule.is_deleted.is_(True),
        db.or_(AutomationRule.session_id.is_(None), AutomationRule.session_id.in_(session_ids)))
    trash_rules, trash_page, trash_pages, trash_total = [], 1, 1, 0
    if can_restore:
        trash_rules, trash_page, trash_pages, trash_total = paginate(trash_query.order_by(AutomationRule.id.desc()), "trash_page")
    session_options = BrewSession.query.filter_by(plant_id=plant_id, is_deleted=False).order_by(BrewSession.id).all()
    return render_template(
        "plant_workspace/_tab_automation.html", plant=plant, rules=rules, logs=logs,
        rules_by_id=rules_by_id, selected_rule=selected_rule,
        rule_option_ids=[row[0] for row in base.with_entities(AutomationRule.id).order_by(AutomationRule.id).all()],
        search=search, active_filter=active, scope_filter=scope, outcome_filter=outcome,
        session_options=session_options, trash_rules=trash_rules, trash_page=trash_page, trash_pages=trash_pages, trash_total=trash_total,
        can_view_logs=can_view_logs, rules_page=rules_page, rules_pages=rules_pages,
        rules_total=rules_total, logs_page=logs_page, logs_pages=logs_pages, logs_total=logs_total,
    )


@plant_workspace_bp.route('/<int:plant_id>/automation-rules', methods=['POST'])
@login_required
@permission_required('automation_rules.create')
def create_workspace_rule(plant_id):
    return _save_workspace_rule(plant_id)


@plant_workspace_bp.route('/<int:plant_id>/automation-rules/<int:rule_id>/edit', methods=['POST'])
@login_required
@permission_required('automation_rules.update')
def edit_workspace_rule(plant_id, rule_id):
    return _save_workspace_rule(plant_id, rule_id)


def _save_workspace_rule(plant_id, rule_id=None):
    from addons.addon_brewstation.features.feature_mash_control.services import workspace_automation_service as service
    try:
        saved = service.save_rule(plant_id, request.form, rule_id)
    except service.WorkspaceAutomationError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), exc.code
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha ao salvar regra no workspace')
        return jsonify(ok=False, error='Não foi possível salvar a regra.'), 500
    return jsonify(ok=True, automation_reload=True, rule_id=saved.id, message='Regra salva inativa. Ative separadamente após conferir sua configuração.')


@plant_workspace_bp.route('/<int:plant_id>/automation-rules/<int:rule_id>/<action>', methods=['POST'])
@login_required
def maintain_workspace_rule(plant_id, rule_id, action):
    permissions = {'activate': 'automation_rules.update', 'deactivate': 'automation_rules.update',
                   'trash': 'automation_rules.trash', 'restore': 'automation_rules.restore'}
    if action not in permissions:
        return jsonify(ok=False, error='Ação inválida.'), 400
    if not current_user.has_permission(permissions[action]):
        return jsonify(ok=False, error='Sem permissão para esta ação.'), 403
    from addons.addon_brewstation.features.feature_mash_control.services import workspace_automation_service as service
    try:
        maintained = service.maintain_rule(plant_id, rule_id, action)
    except service.WorkspaceAutomationError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), exc.code
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha na manutenção de regra')
        return jsonify(ok=False, error='Não foi possível alterar a regra.'), 500
    return jsonify(ok=True, automation_reload=True, rule_id=rule_id if action != 'trash' else None, message=('Regra já estava fora da lixeira; seu estado atual foi preservado.' if maintained.is_active else 'Regra restaurada inativa.') if action == 'restore' else 'Regra atualizada.')


@plant_workspace_bp.route('/<int:plant_id>/sessions/<int:session_id>/runtime/<action>', methods=['POST'])
@login_required
def workspace_session_runtime(plant_id, session_id, action):
    from addons.addon_brewstation.features.feature_mash_control.controller import dashboard_runtime as runtime
    operations = {'advance-step': runtime.advance_step, 'go-back-step': runtime.go_back_step,
                  'resync-steps': runtime.resync_steps, 'toggle-pause': runtime.toggle_pause_session,
                  'stop': runtime.stop_session}
    if action not in operations:
        return jsonify(ok=False, error='Operação inválida.'), 400
    permission = 'brew_sessions.update' if action in ('toggle-pause', 'stop') else 'dashboard_layouts.update'
    if not current_user.has_permission(permission):
        return jsonify(ok=False, error='Sem permissão para esta operação.'), 403
    plant = db.session.get(BrewPlant, plant_id)
    session = db.session.get(BrewSession, session_id)
    if not plant or plant.is_deleted or not session or session.is_deleted or session.plant_id != plant_id:
        return jsonify(ok=False, error='Sessão desta planta não encontrada.'), 404
    if action == 'resync-steps':
        recipe = db.session.get(MashRecipe, session.recipe_id) if session.recipe_id else None
        if not recipe or recipe.is_deleted:
            return jsonify(ok=False, error='Receita disponível não encontrada para ressincronizar.'), 400
    allowed = ('draft', 'active', 'paused') if action == 'resync-steps' else ('active', 'paused') if action in ('toggle-pause', 'stop') else ('active',)
    if session.status not in allowed:
        return jsonify(ok=False, error='Operação indisponível para o status desta sessão.'), 400
    if request.form.get('expected_status') != session.status:
        return jsonify(ok=False, error='O status mudou. Atualize a sessão antes de repetir a operação.'), 409
    if action in ('advance-step', 'go-back-step'):
        operational = BrewSessionStep.query.filter_by(session_id=session_id, is_deleted=False).filter(
            BrewSessionStep.step_type.in_(('mash', 'boil'))).order_by(BrewSessionStep.step_index).all()
        current = next((step for step in operational if step.status == 'active'), None)
        if current is None:
            current = next((step for step in operational if step.status == 'pending'), None)
        if request.form.get('expected_step_id', type=int) != (current.id if current else 0):
            return jsonify(ok=False, error='A etapa mudou. Atualize a sessão antes de repetir a operação.'), 409
    try:
        response = current_app.make_response(operations[action](session_id))
        result = response.get_json(silent=True)
        if response.status_code >= 400 or not result or not result.get('ok'):
            db.session.rollback()
            return response
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha na operação da sessão')
        return jsonify(ok=False, error='Não foi possível concluir a operação.'), 500
    return jsonify(ok=True, message='Operação da sessão concluída.')


@plant_workspace_bp.route('/<int:plant_id>/sessions/<int:session_id>/steps/<int:step_id>/adjust', methods=['POST'])
@login_required
@permission_required('brew_session_steps.update')
def workspace_adjust_step(plant_id, session_id, step_id):
    import math
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service as timeline
    plant = db.session.get(BrewPlant, plant_id)
    session = db.session.get(BrewSession, session_id)
    step = db.session.get(BrewSessionStep, step_id)
    if not plant or plant.is_deleted or not session or session.is_deleted or session.plant_id != plant_id or not step or step.is_deleted or step.session_id != session_id:
        return jsonify(ok=False, error='Etapa desta sessão/planta não encontrada.'), 404
    if session.status not in ('draft', 'active', 'paused') or step.status not in ('pending', 'active'):
        return jsonify(ok=False, error='Somente etapas pendentes ou ativas de sessões abertas podem ser ajustadas.'), 400
    field = request.form.get('field')
    raw = (request.form.get('value') or '').strip()
    if field == 'name':
        if not raw or len(raw) > 100:
            return jsonify(ok=False, error='Informe nome de até 100 caracteres.'), 400
        value = raw
    elif field in ('target_temp', 'duration_seconds'):
        try:
            value = None if field == 'target_temp' and not raw else int(raw) if field == 'duration_seconds' else float(raw)
        except ValueError:
            return jsonify(ok=False, error='Informe um valor numérico válido.'), 400
        if (field == 'duration_seconds' and (value < 0 or value > 2147483647)) or (field == 'target_temp' and value is not None and not math.isfinite(value)):
            return jsonify(ok=False, error='Valor fora do intervalo permitido.'), 400
    else:
        return jsonify(ok=False, error='Campo não ajustável.'), 400
    try:
        if getattr(step, field) != value:
            timeline.adjust_session_step(step_id, field=field, new_value=value, user_id=current_user.id)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha ao ajustar etapa')
        return jsonify(ok=False, error='Não foi possível ajustar a etapa. Nenhuma alteração foi confirmada.'), 500
    return jsonify(ok=True, message='Ajuste da etapa registrado.')


@plant_workspace_bp.route('/<int:plant_id>/dashboard-layouts/<int:layout_id>/standby', methods=['POST'])
@login_required
@permission_required('dashboard_layouts.update')
def configure_dashboard_standby(plant_id, layout_id):
    from addons.addon_brewstation.features.feature_mash_control.services.dashboard_workspace_actions import configure_standby
    try:
        layout = configure_standby(plant_id, layout_id,
            enabled=request.form.get('is_standby_enabled') == 'on',
            seconds=request.form.get('standby_duration_seconds'))
    except LookupError as exc:
        return _workspace_form_error(str(exc), 404, plant_id=plant_id, tab='dashboard')
    except ValueError as exc:
        return _workspace_form_error(str(exc), 400, plant_id=plant_id, tab='dashboard')
    except Exception:
        current_app.logger.exception('Falha ao salvar descanso visual do painel %s', layout_id)
        return _workspace_form_error('Não foi possível salvar o descanso visual. Alterações desfeitas.',
                                     500, plant_id=plant_id, tab='dashboard')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(ok=True, layout_id=layout.id, message='Descanso visual salvo.')
    flash('Descanso visual salvo.', 'success')
    return redirect(url_for('plant_workspace.shell', plant_id=plant_id, tab='dashboard', layout_id=layout.id))
