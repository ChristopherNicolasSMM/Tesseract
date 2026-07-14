"""
addons/addon_brewstation/features/feature_mash_control/controller/dashboard_runtime.py

Telas/rotas do Dashboard de Brassagem de verdade (arquitetura
consolidada em conversa) — NÃO gerado pelo CrudGen, igual em espírito
a automation_engine.py: ponto de extensão manual estável. As telas de
CRUD cru (dashboard_layouts.py/dashboard_widgets.py, geradas) continuam
existindo à parte, pra cadastrar os dados — este arquivo é só o
"executar"/visualizar.
"""
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.services import dashboard_runtime_service as svc

dashboard_runtime_bp = Blueprint(
    "dashboard_runtime", __name__, url_prefix="/brewstation/dashboards"
)


@dashboard_runtime_bp.route("/", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def index():
    """Resolve o layout padrão (is_default=True) ou o primeiro
    disponível e redireciona pra view dele — é o alvo da Transação de
    menu (TX_DASHBOARD_VIEW), que não pode apontar pra um :id
    dinâmico."""
    layout = (
        DashboardLayout.query.filter_by(is_deleted=False, is_default=True).first()
        or DashboardLayout.query.filter_by(is_deleted=False).order_by(DashboardLayout.id).first()
    )
    if not layout:
        flash("Nenhum layout de dashboard cadastrado ainda.", "error")
        return redirect(url_for("dashboard_layouts.manage"))
    return redirect(url_for("dashboard_runtime.view", layout_id=layout.id))


@dashboard_runtime_bp.route("/<int:layout_id>/view", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def view(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        flash("Layout não encontrado.", "error")
        return redirect(url_for("dashboard_layouts.manage"))

    widgets = DashboardWidget.query.filter_by(layout_id=layout.id, is_deleted=False, is_visible=True).all()
    vessels_by_id = {}
    if layout.plant_id:
        for v in BrewPlantVessel.query.filter_by(plant_id=layout.plant_id, is_deleted=False).all():
            vessels_by_id[v.id] = v

    # Achado real (conversa): o campo "Atuador de fluxo" do editor de
    # tubulação era texto livre — vira select, mesma referência fraca
    # de sempre (skill 02, cross-Addon por name), sem FK real.
    from addons.addon_device_manager.root.model.device_function import DeviceFunction
    actuator_functions = DeviceFunction.query.filter_by(category="actuator", is_deleted=False).order_by(DeviceFunction.display_name).all()

    return render_template(
        "dashboards/view.html",
        layout=layout,
        widgets=widgets,
        vessels_by_id=vessels_by_id,
        actuator_functions=actuator_functions,
        all_layouts=DashboardLayout.query.filter_by(is_deleted=False).order_by(DashboardLayout.name).all(),
    )


@dashboard_runtime_bp.route("/<int:layout_id>/snapshot", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def snapshot(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        return jsonify({"error": "Layout não encontrado."}), 404
    return jsonify(svc.get_layout_snapshot(layout))


@dashboard_runtime_bp.route("/widgets/<int:widget_id>/set-value", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.list")
def set_value(widget_id: int):
    widget = DashboardWidget.query.get(widget_id)
    if not widget or widget.is_deleted:
        return jsonify({"ok": False, "error": "Widget não encontrado."}), 404

    payload = request.get_json(silent=True) or {}
    value = payload.get("value")
    role_key = payload.get("role_key")

    ok = svc.set_widget_value(widget, value, role_key=role_key)
    if not ok:
        return jsonify({"ok": False, "error": "Não foi possível acionar — verifique o mapeamento do dispositivo."}), 400
    return jsonify({"ok": True})


@dashboard_runtime_bp.route("/sessions/<int:session_id>/readings", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def readings(session_id: int):
    function_name = request.args.get("function_name")
    window_minutes = request.args.get("window_minutes", default=60, type=int)
    if not function_name:
        return jsonify({"error": "function_name é obrigatório."}), 400
    return jsonify(svc.get_session_readings(session_id, function_name, window_minutes))


# ── Editor visual (conversa — CraftBeerPi como referência) ─────────────────

@dashboard_runtime_bp.route("/widgets/<int:widget_id>/geometry", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.update")
def update_geometry(widget_id: int):
    widget = DashboardWidget.query.get(widget_id)
    if not widget or widget.is_deleted:
        return jsonify({"ok": False, "error": "Widget não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    svc.update_widget_geometry(
        widget,
        x=payload.get("x"), y=payload.get("y"),
        width=payload.get("width"), height=payload.get("height"),
        rotation=payload.get("rotation"),
    )
    return jsonify({"ok": True})


@dashboard_runtime_bp.route("/widgets/<int:widget_id>/config", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.update")
def update_config(widget_id: int):
    widget = DashboardWidget.query.get(widget_id)
    if not widget or widget.is_deleted:
        return jsonify({"ok": False, "error": "Widget não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    svc.update_widget_config(
        widget, label_text=payload.get("label_text"), config_json=payload.get("config_json"),
    )
    return jsonify({"ok": True})


@dashboard_runtime_bp.route("/<int:layout_id>/widgets", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.create")
def create_widget(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        return jsonify({"ok": False, "error": "Layout não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    try:
        widget = svc.create_widget_from_editor(
            layout,
            widget_type=payload.get("widget_type"), label_text=payload.get("label_text") or "",
            x=payload.get("x", 40), y=payload.get("y", 40),
            width=payload.get("width", 220), height=payload.get("height", 220),
            vessel_id=payload.get("vessel_id"), device_function_name=payload.get("device_function_name"),
        )
    except svc.DashboardEditorError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "widget_id": widget.id})


@dashboard_runtime_bp.route("/widgets/<int:widget_id>/delete", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.trash")
def delete_widget(widget_id: int):
    widget = DashboardWidget.query.get(widget_id)
    if not widget or widget.is_deleted:
        return jsonify({"ok": False, "error": "Widget não encontrado."}), 404
    svc.remove_widget_from_editor(widget)
    return jsonify({"ok": True})


@dashboard_runtime_bp.route("/<int:layout_id>/plant-connections", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def update_connections(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        return jsonify({"ok": False, "error": "Layout não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    try:
        svc.update_plant_connections(layout, payload.get("connections") or [])
    except svc.DashboardEditorError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True})
