"""
addons/addon_brewstation/features/feature_mash_control/services/dashboard_runtime_service.py

Runtime do Dashboard de Brassagem (arquitetura consolidada em
conversa — ponto de encontro entre addon_device_manager e
mash_control). NÃO é gerado pelo CrudGen — igual em espírito a
automation_engine.py e device_function_lookup.py: ponto de extensão
manual estável.

Nunca importa nada de addons.addon_device_manager.root.model
diretamente — toda leitura/escrita de valor passa por
device_service (get_value/set_value/find_actor_external_id_by_function_name)
e device_function_lookup (metadado: ícone/unidade/tipo), que devolvem
sempre primitivo/dict, nunca o DeviceActor/DeviceFunction vivo
(skill 02).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget

logger = logging.getLogger(__name__)


def _resolve_value_and_meta(function_name: Optional[str]) -> dict:
    """Valor atual + metadado de exibição (ícone/unidade/tipo) de uma
    function — sempre via service público do device_manager, nunca
    ORM direto (skill 02)."""
    if not function_name:
        return {"value": None, "unit": None, "icon": None, "data_type": None}

    from addons.addon_device_manager.root.services import device_service
    from addons.addon_device_manager.root.services.device_function_lookup import get_function_by_name

    meta = get_function_by_name(function_name) or {}
    external_id = device_service.find_actor_external_id_by_function_name(function_name)
    value = device_service.get_value(external_id) if external_id else None

    return {
        "value": value,
        "unit": meta.get("unit"),
        "icon": meta.get("icon"),
        "data_type": meta.get("data_type"),
        "min_value": meta.get("min_value"),
        "max_value": meta.get("max_value"),
    }


def _resolve_vessel_snapshot(vessel_id: int) -> dict:
    """Pra widget tipo 'vessel' — reaproveita o BrewPlantMapping já
    configurado (role_key -> device_function_name) em vez de duplicar
    a referência no widget."""
    mappings = BrewPlantMapping.query.filter_by(vessel_id=vessel_id, is_deleted=False).all()
    roles = {}
    for m in mappings:
        roles[m.role_key] = {
            "label": m.label_text or m.role_key,
            **_resolve_value_and_meta(m.device_function_name),
        }
    return roles


def get_layout_snapshot(layout: DashboardLayout, session_id_override: Optional[int] = None) -> dict:
    """1 chamada só, devolve o valor atual de TODOS os widgets do
    layout — o front-end faz polling nisso, não 1 request por widget.

    `session_id_override` (conversa — seletor de sessão no Dashboard):
    quando informado, força a sessão usada pros widgets/step_card em
    vez da resolução automática por `status="active"` — útil quando
    há mais de uma sessão pra mesma Planta (histórico, ou duas
    marcadas active por engano) e o usuário quer ver uma específica."""
    active_session = None
    if session_id_override and layout.plant_id:
        candidate = BrewSession.query.filter_by(
            id=session_id_override, plant_id=layout.plant_id, is_deleted=False,
        ).first()
        if candidate:
            active_session = candidate
    if active_session is None and layout.plant_id:
        active_session = _get_active_session_for_plant(layout.plant_id)

    # Disparo automático de alertas (conversa — timeline de etapas):
    # reaproveita este mesmo polling de 3s, sem scheduler novo.
    step_card_data = None
    if active_session:
        from addons.addon_brewstation.features.feature_mash_control.services import recipe_timeline_service
        recipe_timeline_service.check_and_fire_alerts(active_session)
        # Calculado uma vez só — reaproveitado pelo header (novo, conversa
        # — barra de topo unificada) e por qualquer widget step_card no
        # layout, evita rodar a mesma query duas vezes por poll.
        step_card_data = recipe_timeline_service.get_step_card_data(active_session)

    widgets_out = {}
    for widget in DashboardWidget.query.filter_by(layout_id=layout.id, is_deleted=False, is_visible=True).all():
        if widget.widget_type == "vessel" and widget.vessel_id:
            widgets_out[widget.id] = {"roles": _resolve_vessel_snapshot(widget.vessel_id)}
        elif widget.widget_type in ("toggle", "gauge", "digital"):
            widgets_out[widget.id] = _resolve_value_and_meta(widget.device_function_name)
        elif widget.widget_type == "alarm_list":
            widgets_out[widget.id] = _get_active_alarms(layout, widget)
        elif widget.widget_type == "step_card":
            widgets_out[widget.id] = step_card_data or {"current": None, "next": None}
        # "chart" widgets buscam via get_session_readings() à parte (histórico, não snapshot pontual)

    available_sessions = []
    if layout.plant_id:
        recent = (
            BrewSession.query.filter_by(plant_id=layout.plant_id, is_deleted=False)
            .order_by(BrewSession.id.desc())
            .limit(20)
            .all()
        )
        available_sessions = [{"id": s.id, "name": s.name, "status": s.status} for s in recent]

    header = None
    if active_session:
        header = {
            "session_id": active_session.id,
            "session_name": active_session.name,
            "session_status": active_session.status,
            "recipe_name": active_session.recipe.name if active_session.recipe else None,
            "current_step": step_card_data["current"] if step_card_data else None,
        }

    return {
        "widgets": widgets_out,
        "connections": get_plant_connections(layout),
        "available_sessions": available_sessions,
        "active_session_id": active_session.id if active_session else None,
        "active_recipe_id": active_session.recipe_id if active_session else None,
        "header": header,
    }


# Âncora padrão = comportamento antigo (linha reta, saindo do
# centro-base do vasilhame de origem e entrando no centro-topo do
# vasilhame de destino) — conversa "editor de tubulação CAD-like".
# `rx`/`ry` são frações (0–1) da caixa delimitadora do widget do
# vasilhame no layout, não coordenada absoluta — assim a âncora
# acompanha o widget se ele for movido/redimensionado.
_DEFAULT_FROM_ANCHOR = {"rx": 0.5, "ry": 1.0}
_DEFAULT_TO_ANCHOR = {"rx": 0.5, "ry": 0.0}


def _sanitize_anchor(raw: Optional[dict], default: dict) -> dict:
    if not isinstance(raw, dict):
        return dict(default)
    try:
        rx = float(raw.get("rx", default["rx"]))
        ry = float(raw.get("ry", default["ry"]))
    except (TypeError, ValueError):
        return dict(default)
    return {"rx": min(max(rx, 0.0), 1.0), "ry": min(max(ry, 0.0), 1.0)}


def _sanitize_waypoints(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for point in raw:
        if not isinstance(point, dict):
            continue
        try:
            out.append({"x": float(point["x"]), "y": float(point["y"])})
        except (TypeError, ValueError, KeyError):
            continue
    return out


def get_plant_connections(layout: DashboardLayout) -> list[dict]:
    """Lê BrewPlant.plant_schema_json (campo que já existia, nunca
    lido em lugar nenhum antes desta conversa) — cada conexão pode
    trazer `flow_function_name` (atuador que decide se a tubulação
    "flui" ou fica parada).

    `from_anchor`/`to_anchor`/`waypoints` são novos (conversa —
    editor de tubulação CAD-like) e sempre opcionais: conexão salva
    antes desta mudança não tem essas chaves e continua renderizando
    exatamente como antes (âncora fixa, linha reta)."""
    if not layout.plant_id or not layout.plant:
        return []
    schema = layout.plant.plant_schema_json or {}
    connections = schema.get("connections") or []
    out = []
    for conn in connections:
        flow_function_name = conn.get("flow_function_name")
        flowing = False
        if flow_function_name:
            meta = _resolve_value_and_meta(flow_function_name)
            flowing = bool(meta.get("value"))
        out.append({
            "from_vessel_id": conn.get("from_vessel_id"),
            "to_vessel_id": conn.get("to_vessel_id"),
            "flow_function_name": flow_function_name,
            "flowing": flowing,
            "color": conn.get("color") or "#3498db",
            "width": conn.get("width") or 6,
            "from_anchor": _sanitize_anchor(conn.get("from_anchor"), _DEFAULT_FROM_ANCHOR),
            "to_anchor": _sanitize_anchor(conn.get("to_anchor"), _DEFAULT_TO_ANCHOR),
            "waypoints": _sanitize_waypoints(conn.get("waypoints")),
        })
    return out


def _get_active_alarms(layout: DashboardLayout, widget: DashboardWidget) -> dict:
    """
    Timeline de alertas do widget — achado real (conversa): antes só
    devolvia `BrewSessionAlarm` (já disparado), então uma Sessão
    recém-gerada (ainda "draft"/sem `started_at`, ou "active" mas
    ainda longe do tempo do alerta) não mostrava NADA, mesmo com a
    receita/timeline certa por trás — parecia bug, mas era só a
    ausência da parte "agendado/próximo". Agora devolve as duas
    listas: `fired` (BrewSessionAlarm, já disparou) e `upcoming`
    (BrewSessionStep tipo alert, ainda não disparou — com contagem
    regressiva se a sessão já estiver ativa, ou só o rótulo se ainda
    for rascunho).
    """
    max_items = (widget.config_json or {}).get("max_items", 5)
    session_id = (widget.config_json or {}).get("session_id")
    session = None

    if session_id:
        session = BrewSession.query.get(session_id)
    elif layout.plant_id:
        session = _get_active_session_for_plant(layout.plant_id)
        if not session:
            # Sem sessão "active" — cai pra rascunho mais recente da
            # planta, pra timeline aparecer mesmo antes de iniciar.
            session = (
                BrewSession.query
                .filter_by(plant_id=layout.plant_id, status="draft", is_deleted=False)
                .order_by(BrewSession.created_at.desc())
                .first()
            )

    if not session:
        return {"fired": [], "upcoming": []}

    fired = (
        BrewSessionAlarm.query
        .filter_by(session_id=session.id, is_deleted=False, is_acknowledged=False)
        .order_by(BrewSessionAlarm.created_at.desc())
        .limit(max_items)
        .all()
    )

    elapsed_seconds = None
    if session.started_at:
        started_at = session.started_at.replace(tzinfo=None) if session.started_at.tzinfo else session.started_at
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        elapsed_seconds = (now - started_at).total_seconds()

    upcoming_steps = (
        BrewSessionStep.query
        .filter_by(session_id=session.id, step_type="alert", alarm_fired=False, is_deleted=False)
        .order_by(BrewSessionStep.trigger_at_seconds.asc())
        .limit(max_items)
        .all()
    )
    upcoming = []
    for step in upcoming_steps:
        seconds_until = None
        if elapsed_seconds is not None and step.trigger_at_seconds is not None:
            seconds_until = step.trigger_at_seconds - elapsed_seconds
        upcoming.append({
            "id": step.id, "name": step.name, "seconds_until": seconds_until,
        })

    return {
        "fired": [a.to_dict() for a in fired],
        "upcoming": upcoming,
        "session_status": session.status,
    }


def _get_active_session_for_plant(plant_id: int) -> Optional[BrewSession]:
    """Achado real da conversa: sem ORDER BY, `.first()` podia devolver
    uma sessão `active` antiga em vez da mais recente, quando havia
    mais de uma pra mesma Planta (ex.: usuário cria sessão nova e a
    antiga nunca foi encerrada) — sessão nova "não aparecia" no
    Dashboard mesmo estando `active` de verdade."""
    return (
        BrewSession.query.filter_by(plant_id=plant_id, status="active", is_deleted=False)
        .order_by(BrewSession.id.desc())
        .first()
    )


def set_widget_value(widget: DashboardWidget, value, *, role_key: Optional[str] = None) -> bool:
    """
    Aciona um atuador a partir de um clique na tela. Pra widget tipo
    'vessel', `role_key` diz qual papel (ex.: "actor_heat") do
    vasilhame está sendo acionado — resolvido via BrewPlantMapping,
    igual a leitura.
    """
    from addons.addon_device_manager.root.services import device_service

    function_name = widget.device_function_name
    if widget.widget_type == "vessel" and widget.vessel_id:
        if not role_key:
            return False
        mapping = BrewPlantMapping.query.filter_by(
            vessel_id=widget.vessel_id, role_key=role_key, is_deleted=False,
        ).first()
        if not mapping:
            return False
        function_name = mapping.device_function_name

    if not function_name:
        return False

    external_id = device_service.find_actor_external_id_by_function_name(function_name)
    if not external_id:
        return False
    return device_service.set_value(external_id, value)


def get_session_readings(session_id: int, function_name: str, window_minutes: int = 60) -> dict:
    """
    Histórico pro widget tipo 'chart' — decisão registrada em conversa:
    reaproveita BrewSessionLog (source="sensor") em vez de criar uma
    tabela de série temporal nova. Só existe dado enquanto uma Sessão
    de Brassagem está/esteve ativa — fora disso o gráfico fica vazio
    (limitação aceita, documentada).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    logs = (
        BrewSessionLog.query
        .filter(
            BrewSessionLog.session_id == session_id,
            BrewSessionLog.source == "sensor",
            BrewSessionLog.created_at >= cutoff,
            BrewSessionLog.is_deleted.is_(False),
        )
        .order_by(BrewSessionLog.created_at.asc())
        .all()
    )
    points = [
        {"t": log.created_at.isoformat(), "v": log.detail_json.get("value")}
        for log in logs
        if (log.detail_json or {}).get("function_name") == function_name
    ]
    return {"function_name": function_name, "points": points}


# ── Editor visual (conversa — CraftBeerPi como referência): modo edição,   ──
# ── arrastar/redimensionar, botão direito (configurações/remover), pipes  ──

_VALID_WIDGET_TYPES = ("vessel", "toggle", "gauge", "digital", "alarm_list", "chart", "step_card", "text", "image")
_VALID_SVG_SHAPES = ("mash_tun", "boil_kettle", "hlt", "fermenter", "whirlpool", "generic")


class DashboardEditorError(Exception):
    pass


def update_widget_geometry(widget: DashboardWidget, *, x=None, y=None, width=None, height=None, rotation=None) -> None:
    """Arrastar/redimensionar no editor — só a posição/tamanho, nunca o
    tipo/referência do widget (isso é 'Configurações', não 'mover')."""
    if x is not None:
        widget.x = x
    if y is not None:
        widget.y = y
    if width is not None:
        widget.width = max(40, width)  # nunca deixa colapsar a 0 por um drag descuidado
    if height is not None:
        widget.height = max(40, height)
    if rotation is not None:
        widget.rotation = rotation
    db.session.commit()


def update_widget_config(widget: DashboardWidget, *, label_text=None, config_json=None,
                          vessel_id=None, device_function_name=None, clear_reference=False) -> None:
    """Painel lateral do editor visual (conversa — Ponto 3, substituiu o
    antigo modal de 'Configurações' por completo). `vessel_id`/
    `device_function_name` agora PODEM ser setados aqui — mudança de
    decisão em relação à versão anterior: widget nasce solto ao ser
    arrastado da paleta (sem vínculo), e o painel é o lugar onde o
    primeiro vínculo é feito. `clear_reference=True` limpa ambos (ex.:
    usuário troca o tipo de referência). A tela de CRUD separada
    (`/dashboard-widgets/<id>`) continua existindo e funcionando igual,
    pra edição em lote/tabular."""
    if label_text is not None:
        widget.label_text = label_text
    if config_json is not None:
        merged = dict(widget.config_json or {})
        merged.update(config_json)
        widget.config_json = merged
    if clear_reference:
        widget.vessel_id = None
        widget.device_function_name = None
    else:
        if vessel_id is not None:
            widget.vessel_id = vessel_id
        if device_function_name is not None:
            widget.device_function_name = device_function_name
    db.session.commit()


def create_widget_from_editor(layout: DashboardLayout, *, widget_type: str, label_text: str,
                               x: int, y: int, width: int = 220, height: int = 220,
                               vessel_id: Optional[int] = None,
                               device_function_name: Optional[str] = None) -> DashboardWidget:
    if widget_type not in _VALID_WIDGET_TYPES:
        raise DashboardEditorError(f"Tipo de widget inválido: {widget_type}")

    max_z = db.session.query(db.func.max(DashboardWidget.z_index)).filter_by(
        layout_id=layout.id, is_deleted=False,
    ).scalar() or 0

    widget = DashboardWidget(
        layout_id=layout.id, widget_type=widget_type, label_text=label_text,
        x=x, y=y, width=width, height=height, z_index=max_z + 1,
        vessel_id=vessel_id if widget_type == "vessel" else None,
        device_function_name=device_function_name if widget_type in ("toggle", "gauge", "digital", "chart") else None,
    )
    db.session.add(widget)
    db.session.commit()
    return widget


def remove_widget_from_editor(widget: DashboardWidget) -> None:
    """Soft-delete — mesmo padrão do resto do projeto (skill 02).
    Reaproveitável (aparece de novo se restaurado pela tela de CRUD,
    já que o editor visual não tem lixeira própria)."""
    widget.is_deleted = True
    widget.deleted_at = datetime.now(timezone.utc)
    db.session.commit()


def update_plant_connections(layout: DashboardLayout, connections: list[dict]) -> None:
    """Editor de tubulação — sobrescreve `plant.plant_schema_json`
    inteiro (lista pequena, não vale a pena granularizar por conexão
    individual). Cada item aceita `color`/`width` além de
    `from_vessel_id`/`to_vessel_id`/`flow_function_name` (mesmo
    formato já usado por `get_plant_connections()` e pelo importador
    do bridge) e, desde a conversa do editor CAD-like,
    `from_anchor`/`to_anchor`/`waypoints` (opcionais — sanitizados
    aqui antes de persistir, mesma regra da leitura)."""
    if not layout.plant_id or not layout.plant:
        raise DashboardEditorError("Este layout não está associado a nenhuma Planta.")
    sanitized = []
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        sanitized.append({
            "from_vessel_id": conn.get("from_vessel_id"),
            "to_vessel_id": conn.get("to_vessel_id"),
            "flow_function_name": conn.get("flow_function_name"),
            "color": conn.get("color") or "#3498db",
            "width": conn.get("width") or 6,
            "from_anchor": _sanitize_anchor(conn.get("from_anchor"), _DEFAULT_FROM_ANCHOR),
            "to_anchor": _sanitize_anchor(conn.get("to_anchor"), _DEFAULT_TO_ANCHOR),
            "waypoints": _sanitize_waypoints(conn.get("waypoints")),
        })
    layout.plant.plant_schema_json = {"connections": sanitized}
    db.session.commit()
