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

import os
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import login_required

from core.permissions import permission_required
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.services import dashboard_runtime_service as svc
from core.db import db

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


def _build_dashboard_view_context(layout: DashboardLayout, *, is_fragment: bool = False) -> dict:
    """Contexto de `dashboards/view.html`/`_fragment.html` — extraído
    pra função própria porque agora tem dois consumidores: a rota
    `view()` (tela cheia) e a aba Dashboard do workspace consolidado
    por Planta (`plant_workspace.py`, fragmento AJAX)."""
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
    device_functions = DeviceFunction.query.filter_by(is_deleted=False).order_by(DeviceFunction.category, DeviceFunction.display_name).all()

    return dict(
        layout=layout,
        widgets=widgets,
        vessels_by_id=vessels_by_id,
        actuator_functions=actuator_functions,
        device_functions=device_functions,
        all_layouts=DashboardLayout.query.filter_by(is_deleted=False).order_by(DashboardLayout.name).all(),
        is_fragment=is_fragment,
    )


@dashboard_runtime_bp.route("/<int:layout_id>/view", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def view(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        flash("Layout não encontrado.", "error")
        return redirect(url_for("dashboard_layouts.manage"))
    return render_template("dashboards/view.html", **_build_dashboard_view_context(layout))


@dashboard_runtime_bp.route("/<int:layout_id>/snapshot", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def snapshot(layout_id: int):
    layout = DashboardLayout.query.get(layout_id)
    if not layout or layout.is_deleted:
        return jsonify({"error": "Layout não encontrado."}), 404
    session_id_override = request.args.get("session_id", type=int)
    return jsonify(svc.get_layout_snapshot(layout, session_id_override=session_id_override))


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

    result = svc.set_widget_value(widget, value, role_key=role_key)
    if not result["ok"]:
        return jsonify({
            "ok": False,
            "error": result["error"] or "Não foi possível acionar — verifique o mapeamento do dispositivo.",
            "mqtt_connected": result["mqtt_connected"],
        }), 400
    return jsonify({"ok": True, "mqtt_connected": result["mqtt_connected"]})


@dashboard_runtime_bp.route("/plants/<int:plant_id>/device-status", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def plant_device_status(plant_id: int):
    """Backend do widget `device_status` — inventário completo de
    sensores/atuadores mapeados na Planta (não depende de layout_id,
    é plant-wide, igual ao `comm-log` abaixo)."""
    return jsonify(svc.get_plant_device_status(plant_id))


@dashboard_runtime_bp.route("/mappings/<int:mapping_id>/set-value", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.list")
def mapping_set_value(mapping_id: int):
    """Acionamento a partir de um card do widget `device_status` —
    equivalente a `set_value()` acima, mas resolvido por
    `BrewPlantMapping.id` em vez de `widget_id` (não existe
    DashboardWidget por trás de um item deste painel)."""
    payload = request.get_json(silent=True) or {}
    result = svc.set_mapping_value(mapping_id, payload.get("value"), plant_id=payload.get("plant_id"))
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)


@dashboard_runtime_bp.route("/plants/<int:plant_id>/comm-log", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def plant_comm_log(plant_id: int):
    """Backend do widget `comm_log` — combina auditoria de ações
    (BrewSessionLog) com o log MQTT bruto do addon_device_manager.
    `action_limit`/`mqtt_limit` na querystring controlam quanto vem
    de cada fonte (o front chama isso no próprio intervalo
    configurável do widget, não fixo aqui)."""
    action_limit = request.args.get("action_limit", default=100, type=int)
    mqtt_limit = request.args.get("mqtt_limit", default=200, type=int)
    return jsonify(svc.get_communication_log(plant_id, action_limit=action_limit, mqtt_raw_limit=mqtt_limit))


@dashboard_runtime_bp.route("/sessions/<int:session_id>/readings", methods=["GET"])
@login_required
@permission_required("dashboard_layouts.list")
def readings(session_id: int):
    function_name = request.args.get("function_name")
    window_minutes = request.args.get("window_minutes", default=60, type=int)
    if not function_name:
        return jsonify({"error": "function_name é obrigatório."}), 400
    return jsonify(svc.get_session_readings(session_id, function_name, window_minutes))


# ── Card de Etapa (conversa — Ponto 2) ──────────────────────────────────────

@dashboard_runtime_bp.route("/sessions/<int:session_id>/advance-step", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def advance_step(session_id: int):
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    try:
        data = recipe_timeline_service.confirm_and_advance_step(session_id)
    except recipe_timeline_service.RecipeTimelineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **data})


@dashboard_runtime_bp.route("/sessions/<int:session_id>/go-back-step", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def go_back_step(session_id: int):
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    try:
        data = recipe_timeline_service.go_back_step(session_id)
    except recipe_timeline_service.RecipeTimelineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **data})


@dashboard_runtime_bp.route("/sessions/<int:session_id>/resync-steps", methods=["POST"])
@login_required
@permission_required("dashboard_layouts.update")
def resync_steps(session_id: int):
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    try:
        result = recipe_timeline_service.resync_session_steps(session_id)
    except recipe_timeline_service.RecipeTimelineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **result})


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
        vessel_id=payload.get("vessel_id"), device_function_name=payload.get("device_function_name"),
        clear_reference=bool(payload.get("clear_reference")),
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


# ── Upload de imagem pro widget "image" (conversa — Ponto 3 + ajustes) ──────
# Salva em feature_mash_control/imgs/ (fora do static/ compartilhado do
# Core, por pedido explícito) — não em /static/ porque essas imagens são
# conteúdo do usuário, não asset versionado do código.
_IMGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "imgs")
_ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def _allowed_image_filename(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_IMAGE_EXTENSIONS


@dashboard_runtime_bp.route("/upload-image", methods=["POST"])
@login_required
@permission_required("dashboard_widgets.update")
def upload_image():
    """Recebe o arquivo do painel lateral do widget Imagem, salva com
    nome gerado (uuid — nunca confia no nome original, evita colisão
    e path traversal) e devolve a URL já pronta pra preencher o campo
    de URL sozinho."""
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Nenhum arquivo enviado."}), 400
    if not _allowed_image_filename(file.filename):
        return jsonify({"ok": False, "error": "Formato não permitido. Use png, jpg, jpeg, gif, webp ou svg."}), 400
    os.makedirs(_IMGS_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(_IMGS_DIR, filename))
    return jsonify({"ok": True, "url": url_for("dashboard_runtime.serve_image", filename=filename)})


@dashboard_runtime_bp.route("/imgs/<path:filename>", methods=["GET"])
@login_required
def serve_image(filename: str):
    return send_from_directory(_IMGS_DIR, filename)


@dashboard_runtime_bp.route("/sessions/<int:session_id>/toggle-pause", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
def toggle_pause_session(session_id: int):
    """Barra de topo unificada (conversa — referência visual): botão de
    pausar/retomar. Alterna só entre `active`/`paused` — não mexe em
    nenhum outro status (`draft`/`completed`/`aborted` ficam de fora,
    o botão nem aparece nesses casos no front). Reversível a qualquer
    momento, sem confirmação (diferente de "parar"). A lógica real de
    congelar/deslocar o tempo mora em
    `recipe_timeline_service.toggle_pause_session()` — achado real:
    só trocar o status aqui não bastava, o timer da etapa continuava
    correndo enquanto "pausada"."""
    from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
    session = BrewSession.query.get(session_id)
    if not session or session.is_deleted:
        return jsonify({"ok": False, "error": "Sessão não encontrada."}), 404
    if session.status not in ("active", "paused"):
        return jsonify({"ok": False, "error": f"Sessão está '{session.status}', não dá pra pausar/retomar."}), 400
    new_status = recipe_timeline_service.toggle_pause_session(session)
    return jsonify({"ok": True, "status": new_status})


@dashboard_runtime_bp.route("/sessions/<int:session_id>/stop", methods=["POST"])
@login_required
@permission_required("brew_sessions.update")
def stop_session(session_id: int):
    """Barra de topo unificada — botão "Parar". Marca a sessão como
    `completed` (a brassagem terminou, não foi abortada por erro —
    diferente de `aborted`, que continua só disponível pela tela
    completa de Sessões pra quando for de fato um problema). O
    front-end pede confirmação antes de chamar esta rota — ação não
    reversível pelo botão (dá pra reverter manualmente via
    /brew-sessions/<id>, mudando o status de novo)."""
    session = BrewSession.query.get(session_id)
    if not session or session.is_deleted:
        return jsonify({"ok": False, "error": "Sessão não encontrada."}), 404
    if session.status not in ("active", "paused"):
        return jsonify({"ok": False, "error": f"Sessão está '{session.status}', não dá pra parar."}), 400
    session.status = "completed"
    db.session.commit()
    return jsonify({"ok": True, "status": session.status})
