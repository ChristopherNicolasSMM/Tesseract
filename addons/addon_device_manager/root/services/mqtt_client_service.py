"""
addons/addon_device_manager/root/services/mqtt_client_service.py

Cliente MQTT do addon_device_manager (decisão 2.3 do documento de
arquitetura — Opção A, MQTT dentro do próprio Addon).

Correção de protocolo registrada em 2026-06-26 (ver
docs/skills/05-proposta-addon-device-manager-e-mqtt.md, seção 5.3):
MQTT permite só UM Last Will and Testament por conexão de cliente —
não é possível registrar um LWT por atuador. Desenho corrigido: um
único LWT agregado, publicado no "status topic", com payload JSON
listando todos os atuadores de risco (is_risk=true) e seus
failsafe_value. Quem aplica o fail-safe de fato é o lado hardware
(`tesseract-device-bridge`, repositório separado) assinando esse
tópico e reagindo a status="offline" — não o broker republicando N
comandos sozinho.

Este módulo NÃO conecta automaticamente ao importar — startup é
explícito via start() (chamado pelo entrypoint da aplicação, fora do
escopo de testes unitários, que não têm broker disponível).
"""
from __future__ import annotations

import json
import logging
import os
import threading

import paho.mqtt.client as mqtt

from core.db import db
from addons.addon_device_manager.root.model.device_actor import DeviceActor

logger = logging.getLogger("addon_device_manager.mqtt")

_client: mqtt.Client | None = None
_lock = threading.Lock()


def _topic_prefix() -> str:
    return os.environ.get("MQTT_TOPIC_PREFIX", "tesseract")


def _full_topic(relative_topic: str) -> str:
    """Junta o topic_prefix com um tópico relativo guardado em config_json."""
    prefix = _topic_prefix().rstrip("/")
    return f"{prefix}/{relative_topic.lstrip('/')}"


def status_topic() -> str:
    return _full_topic("system/tesseract/status")


def build_lwt_payload(app=None) -> str:
    """
    Monta o payload JSON do LWT agregado: todos os DeviceActor com
    is_risk=true e seu command_topic + failsafe_value. Função pura
    (sem efeito colateral de rede) — testável sem broker.
    """
    query = DeviceActor.query.filter_by(is_risk=True, is_deleted=False)
    actuators = []
    for actor in query.all():
        mqtt_config = (actor.get_config() or {}).get("mqtt_config") or {}
        command_topic = mqtt_config.get("command_topic")
        if not command_topic:
            continue  # sem tópico configurado, nada a fazer no fail-safe
        actuators.append({
            "external_id": actor.external_id,
            "name": actor.name,
            "command_topic": _full_topic(command_topic),
            "failsafe_value": actor.failsafe_value,
        })
    return json.dumps({"status": "offline", "failsafe_actuators": actuators}, ensure_ascii=False)


def build_online_payload() -> str:
    return json.dumps({"status": "online"}, ensure_ascii=False)


def _on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    logger.info("Conectado ao broker MQTT (reason_code=%s).", reason_code)
    client.publish(status_topic(), build_online_payload(), qos=1, retain=True)

    app = userdata.get("app")
    with app.app_context():
        for actor in DeviceActor.query.filter_by(is_deleted=False, is_active=True).all():
            mqtt_config = (actor.get_config() or {}).get("mqtt_config") or {}
            state_topic = mqtt_config.get("state_topic")
            if state_topic:
                client.subscribe(_full_topic(state_topic), qos=mqtt_config.get("qos", 0))


def _on_message(client: mqtt.Client, userdata, msg) -> None:
    app = userdata.get("app")
    with app.app_context():
        from addons.addon_device_manager.root.services import device_service

        actor = _find_actor_by_state_topic(msg.topic)
        if actor is None:
            logger.warning("Mensagem MQTT em tópico sem DeviceActor correspondente: %s", msg.topic)
            return
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            logger.error("Payload MQTT não-UTF8 em %s, ignorado.", msg.topic)
            return
        device_service.update_from_mqtt(actor, payload)


def _find_actor_by_state_topic(full_topic: str) -> DeviceActor | None:
    for actor in DeviceActor.query.filter_by(is_deleted=False).all():
        mqtt_config = (actor.get_config() or {}).get("mqtt_config") or {}
        state_topic = mqtt_config.get("state_topic")
        if state_topic and _full_topic(state_topic) == full_topic:
            return actor
    return None


def start(app) -> mqtt.Client:
    """
    Inicia o cliente MQTT e conecta ao broker (não-bloqueante —
    paho usa loop em thread própria via loop_start()). Idempotente:
    chamadas repetidas reusam o cliente já iniciado.
    """
    global _client
    with _lock:
        if _client is not None:
            return _client

        host = os.environ.get("MQTT_BROKER_HOST", "localhost")
        port = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
        client_id = os.environ.get("MQTT_CLIENT_ID", "tesseract_device_manager")
        username = os.environ.get("MQTT_USERNAME")
        password = os.environ.get("MQTT_PASSWORD")

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
            userdata={"app": app},
        )
        if username:
            client.username_pw_set(username, password)

        with app.app_context():
            client.will_set(status_topic(), build_lwt_payload(app), qos=1, retain=True)

        client.on_connect = _on_connect
        client.on_message = _on_message

        client.connect(host, port, keepalive=30)
        client.loop_start()

        _client = client
        logger.info("Cliente MQTT iniciado (%s:%s, client_id=%s).", host, port, client_id)
        return client


def stop() -> None:
    global _client
    with _lock:
        if _client is not None:
            _client.loop_stop()
            _client.disconnect()
            _client = None


def publish(relative_topic: str, value, *, qos: int = 0, retain: bool = False) -> bool:
    """Publica um valor num tópico relativo (resolvido com topic_prefix)."""
    if _client is None:
        logger.debug("publish() chamado sem cliente MQTT ativo — ignorado (%s).", relative_topic)
        return False
    payload = value if isinstance(value, str) else json.dumps(value)
    _client.publish(_full_topic(relative_topic), payload, qos=qos, retain=retain)
    return True


def is_connected() -> bool:
    return _client is not None and _client.is_connected()
