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

from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
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


def get_layout_snapshot(layout: DashboardLayout) -> dict:
    """1 chamada só, devolve o valor atual de TODOS os widgets do
    layout — o front-end faz polling nisso, não 1 request por widget."""
    widgets_out = {}
    for widget in DashboardWidget.query.filter_by(layout_id=layout.id, is_deleted=False, is_visible=True).all():
        if widget.widget_type == "vessel" and widget.vessel_id:
            widgets_out[widget.id] = {"roles": _resolve_vessel_snapshot(widget.vessel_id)}
        elif widget.widget_type in ("toggle", "gauge", "digital"):
            widgets_out[widget.id] = _resolve_value_and_meta(widget.device_function_name)
        elif widget.widget_type == "alarm_list":
            widgets_out[widget.id] = {"alarms": _get_active_alarms(layout, widget)}
        # "chart" widgets buscam via get_session_readings() à parte (histórico, não snapshot pontual)

    active_session = _get_active_session_for_plant(layout.plant_id) if layout.plant_id else None

    return {
        "widgets": widgets_out,
        "connections": get_plant_connections(layout),
        "active_session_id": active_session.id if active_session else None,
    }


def get_plant_connections(layout: DashboardLayout) -> list[dict]:
    """Lê BrewPlant.plant_schema_json (campo que já existia, nunca
    lido em lugar nenhum antes desta conversa) — cada conexão pode
    trazer `flow_function_name` (atuador que decide se a tubulação
    "flui" ou fica parada)."""
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
        })
    return out


def _get_active_alarms(layout: DashboardLayout, widget: DashboardWidget) -> list[dict]:
    max_items = (widget.config_json or {}).get("max_items", 5)
    session_id = (widget.config_json or {}).get("session_id")
    query = BrewSessionAlarm.query.filter_by(is_deleted=False, is_acknowledged=False)
    if session_id:
        query = query.filter_by(session_id=session_id)
    elif layout.plant_id:
        active_session = _get_active_session_for_plant(layout.plant_id)
        if active_session:
            query = query.filter_by(session_id=active_session.id)
        else:
            return []
    alarms = query.order_by(BrewSessionAlarm.created_at.desc()).limit(max_items).all()
    return [a.to_dict() for a in alarms]


def _get_active_session_for_plant(plant_id: int) -> Optional[BrewSession]:
    return BrewSession.query.filter_by(plant_id=plant_id, status="active", is_deleted=False).first()


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
