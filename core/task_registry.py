"""
core/task_registry.py

Ponto de extensão estável para Addons registrarem funções Python
elegíveis como ScheduledTask (task_type="python_call"). Nunca editar
TaskService.TASK_REGISTRY diretamente de fora — sempre via
register_task(), para manter um único lugar de validação.

Uso típico, dentro de um addon.py:

    from core.task_registry import register_task

    class AddonDeviceManager(AddonBase):
        def register_routes(self, app) -> None:
            ...
            register_task("device_manager.mqtt_reconnect", _reconnect_mqtt)
"""
from __future__ import annotations

from typing import Callable


def register_task(name: str, fn: Callable) -> None:
    """
    Registra `fn` sob a chave `name` — convenção sugerida:
    `[addon_ou_modulo].[acao]` (ex.: "device_manager.mqtt_reconnect"),
    paralela à convenção de evento do EventBus (skill 00), para que o
    `target` de uma ScheduledTask seja legível na UI do monitor.
    """
    from services.core import task_service
    task_service.TASK_REGISTRY[name] = fn


def list_registered_tasks() -> list[str]:
    """Usado pela UI do monitor para sugerir `target` válidos ao criar uma task python_call."""
    from services.core import task_service
    return sorted(task_service.TASK_REGISTRY.keys())
