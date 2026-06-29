"""
addons/addon_brewstation/features/feature_mash_control/services/automation_engine.py

Motor de automação reativo (Fase E, Opção 1 — decisão de 2026-06-29).
Sensor -> condição -> ator: avalia AutomationRule a cada mudança de
valor de QUALQUER DeviceActor (via device_service.on_any_change),
não por polling — não há scheduler envolvido, é puramente
event-driven sobre o que já chega via device_service/mqtt_client_service.

Nunca importa nada de addons.addon_device_manager.root.model
diretamente, nem recebe objetos ORM de lá (skill 02 — cross-Addon só
via service público, com dados primitivos/dict, nunca objeto vivo).
Toda interação passa por device_service (get_value/set_value/
on_any_change/find_actor_external_id_by_function_name), que entrega
sempre string/valor primitivo, nunca o DeviceActor em si.

Registro: chamado uma única vez por
FeatureMashControl.register_routes() — ver feature.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.db import db
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
from addons.addon_brewstation.features.feature_mash_control.model.automation_rule_log import AutomationRuleLog

logger = logging.getLogger(__name__)

_OPERATORS = {
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
}

_registered = False


def register() -> None:
    """
    Inscreve _on_device_value_changed em device_service.on_any_change().
    Idempotente — chamar mais de uma vez (ex.: testes recriando a app)
    não duplica a inscrição.
    """
    global _registered
    if _registered:
        return
    from addons.addon_device_manager.root.services import device_service
    device_service.on_any_change(_on_device_value_changed)
    _registered = True


def _on_device_value_changed(sensor_function_name: str | None, value) -> None:
    """
    `sensor_function_name` já vem como string (referência fraca,
    skill 02) — device_service nunca expõe o objeto DeviceActor pra
    fora do próprio módulo.
    """
    if sensor_function_name is None:
        return

    rules = AutomationRule.query.filter_by(
        sensor_function_name=sensor_function_name, is_active=True, is_deleted=False,
    ).all()
    for rule in rules:
        _evaluate_rule(rule, value)


def _evaluate_rule(rule: AutomationRule, sensor_value) -> None:
    if _in_cooldown(rule):
        return

    try:
        numeric_value = float(sensor_value)
    except (TypeError, ValueError):
        logger.warning(
            "AutomationRule '%s': valor de sensor não-numérico (%r), ignorado.",
            rule.name, sensor_value,
        )
        return

    operator_fn = _OPERATORS.get(rule.condition_operator)
    if operator_fn is None:
        logger.warning("AutomationRule '%s': operador desconhecido '%s'.", rule.name, rule.condition_operator)
        return

    if not operator_fn(numeric_value, rule.condition_value):
        return

    _trigger_rule(rule, numeric_value)


def _in_cooldown(rule: AutomationRule) -> bool:
    if not rule.last_triggered_at or not rule.cooldown_seconds:
        return False
    elapsed = (datetime.now(timezone.utc) - rule.last_triggered_at).total_seconds()
    return elapsed < rule.cooldown_seconds


def _resolve_target_value(rule: AutomationRule):
    if rule.actor_action == "ON":
        return True
    if rule.actor_action == "OFF":
        return False
    if rule.actor_action == "SET_VALUE":
        return rule.actor_value
    if rule.actor_action == "TOGGLE":
        from addons.addon_device_manager.root.services import device_service
        current = device_service.get_value(rule.actor_function_name)
        return not bool(current)
    raise ValueError(f"actor_action '{rule.actor_action}' desconhecido.")


def _trigger_rule(rule: AutomationRule, sensor_value: float) -> None:
    from addons.addon_device_manager.root.services import device_service

    success = True
    error_message = None
    action_taken = f"{rule.actor_action}"

    try:
        target_identifier = device_service.find_actor_external_id_by_function_name(rule.actor_function_name)
        if target_identifier is None:
            raise ValueError(f"Nenhum DeviceActor encontrado para a function '{rule.actor_function_name}'.")

        target_value = _resolve_target_value(rule)
        ok = device_service.set_value(target_identifier, target_value)
        if not ok:
            raise ValueError(f"device_service.set_value falhou para '{target_identifier}'.")
        action_taken = f"{rule.actor_action} -> {target_value}"

    except Exception as e:
        success = False
        error_message = str(e)[:500]
        logger.exception("Erro ao disparar AutomationRule '%s'", rule.name)

    rule.last_triggered_at = datetime.now(timezone.utc)
    rule.trigger_count = (rule.trigger_count or 0) + 1
    db.session.add(AutomationRuleLog(
        rule_id=rule.id,
        sensor_value_at_trigger=sensor_value,
        action_taken=action_taken,
        success=success,
        error_message=error_message,
    ))
    db.session.commit()
