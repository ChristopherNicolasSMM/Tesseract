"""
core/event_bus.py

Pub/sub simples, em memória, síncrono. Nome de evento segue a convenção
da skill 00: namespace por ponto, presente do indicativo no domínio +
passado na ação (ex.: "core.module.activated").

Por que síncrono e em memória nesta fase: não há ainda nenhum Addon que
precise de processamento assíncrono/distribuído. Trocar por uma fila
real (Redis, etc.) é uma decisão de Fase futura, não de Fase 1 — não
adiantar dependência.

Cada módulo (Core, Addon, Plugin) pode `subscribe` a um evento sem
acoplamento direto ao publicador — é o único canal permitido de
comunicação entre Addons diferentes (skill 02, seção de FK entre
módulos).
"""
import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Callable) -> None:
        self._listeners[event_name].append(handler)
        logger.debug(
            "Listener registrado: %s -> %s", event_name, handler.__qualname__
        )

    def publish(self, event_name: str, **payload) -> None:
        handlers = self._listeners.get(event_name, [])
        logger.debug(
            "Evento publicado: %s | payload=%s | %d listener(s)",
            event_name, payload, len(handlers),
        )
        for handler in handlers:
            try:
                handler(**payload)
            except Exception:
                # Um listener com erro nunca pode quebrar o publicador
                # nem os demais listeners do mesmo evento.
                logger.exception(
                    "Erro no listener %s para o evento %s",
                    handler.__qualname__, event_name,
                )


event_bus = EventBus()


def register_example_listener() -> None:
    """
    Listener de exemplo, registrado no boot do Core (ver app_factory.py).

    Existe só para provar que a infraestrutura de publish/subscribe
    funciona de ponta a ponta nesta fase — não é lógica de negócio.
    Remover quando o primeiro Addon real (Fase 5) tiver seus próprios
    listeners.
    """
    def _on_module_activated(module_name: str, module_type: str) -> None:
        logger.info(
            "[listener de exemplo] módulo ativado: %s (%s)",
            module_name, module_type,
        )

    event_bus.subscribe("core.module.activated", _on_module_activated)
