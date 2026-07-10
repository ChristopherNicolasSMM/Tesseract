"""
addons/addon_brewstation/features/feature_mash_control/services/dashboard_reading_logger.py

Grava leitura de sensor em BrewSessionLog (source="sensor") — decisão
registrada em conversa: reaproveita o log de sessão já existente em
vez de criar uma tabela de série temporal nova. Só grava quando existe
uma Sessão de Brassagem ATIVA usando a planta daquele sensor — fora
disso a leitura é ignorada (ninguém quer histórico de quando não tem
brassagem rolando).

Mesmo padrão de automation_engine.py: inscreve-se no EventBus do Core
(core/event_bus.py, evento "device_manager.actor.value_changed"),
nunca importa nada de addons.addon_device_manager.root.model
diretamente (skill 02).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core.db import db
from core.event_bus import event_bus
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog

logger = logging.getLogger(__name__)

EVENT_ACTOR_VALUE_CHANGED = "device_manager.actor.value_changed"

# Throttle — evita gravar 1 linha a cada leitura (pode chegar a cada
# poucos segundos via MQTT); o gráfico não precisa de mais resolução
# que isso.
_THROTTLE_SECONDS = 30

_registered = False


def register() -> None:
    """Idempotente — mesma proteção de automation_engine.register()."""
    global _registered
    if _registered:
        return
    event_bus.subscribe(EVENT_ACTOR_VALUE_CHANGED, _on_device_value_changed)
    _registered = True


def _on_device_value_changed(function_name: str | None = None, value=None) -> None:
    """Assinatura em keyword args — mesmo motivo documentado em
    automation_engine.py (EventBus.publish despacha via **payload)."""
    if function_name is None:
        return

    mappings = (
        BrewPlantMapping.query
        .filter_by(device_function_name=function_name, is_deleted=False)
        .all()
    )
    for mapping in mappings:
        _maybe_log_reading(mapping, function_name, value)


def _maybe_log_reading(mapping: BrewPlantMapping, function_name: str, value) -> None:
    vessel = BrewPlantVessel.query.get(mapping.vessel_id)
    if not vessel:
        return

    session = (
        BrewSession.query
        .filter_by(plant_id=vessel.plant_id, status="active", is_deleted=False)
        .first()
    )
    if not session:
        return

    if _in_throttle_window(session.id, function_name):
        return

    db.session.add(BrewSessionLog(
        session_id=session.id,
        log_level="info",
        source="sensor",
        message=f"{function_name} = {value}",
        detail_json={"function_name": function_name, "value": value},
    ))
    db.session.commit()


def _in_throttle_window(session_id: int, function_name: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_THROTTLE_SECONDS)
    recent = (
        BrewSessionLog.query
        .filter(
            BrewSessionLog.session_id == session_id,
            BrewSessionLog.source == "sensor",
            BrewSessionLog.created_at >= cutoff,
        )
        .order_by(BrewSessionLog.created_at.desc())
        .limit(20)  # janela curta, poucas linhas — filtra em Python, sem índice em JSON
        .all()
    )
    return any((log.detail_json or {}).get("function_name") == function_name for log in recent)
