"""Safe, transient diagnostics for Device Manager REST and MQTT flows."""
from __future__ import annotations

import ipaddress
import json
import math
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from addons.addon_device_manager.root.model.device_actor import DeviceActor
from addons.addon_device_manager.root.services import device_service, mqtt_client_service

REST_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
REST_MAX_BODY = 32_768
REST_MAX_RESPONSE = 65_536
REST_TIMEOUT_SECONDS = 8
MQTT_TEST_MAX_PAYLOAD = 32_768
_BLOCKED_HEADERS = {"host", "content-length", "connection", "transfer-encoding", "proxy-authorization", "proxy-connection", "upgrade"}
_PRIVATE_V4 = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
_PRIVATE_V6 = (ipaddress.ip_network("fc00::/7"),)


class CommunicationTestError(ValueError):
    pass


def broker_settings() -> dict:
    return {
        "enabled": os.environ.get("MQTT_ENABLED", "false").lower() == "true",
        "connected": mqtt_client_service.is_connected(),
        "host": os.environ.get("MQTT_BROKER_HOST", "localhost"),
        "port": int(os.environ.get("MQTT_BROKER_PORT", "1883")),
        "client_id": os.environ.get("MQTT_CLIENT_ID", "tesseract_device_manager"),
        "topic_prefix": os.environ.get("MQTT_TOPIC_PREFIX", "tesseract").strip("/"),
        "username_configured": bool(os.environ.get("MQTT_USERNAME")),
    }


def _connected(reason_code) -> bool:
    try:
        return int(reason_code) == 0
    except (TypeError, ValueError):
        return not getattr(reason_code, "is_failure", True)


def probe_mqtt_broker(timeout: float = 4.0) -> dict:
    """Open a one-shot MQTT client and self-publish to a unique diagnostics topic."""
    if not broker_settings()["enabled"]:
        return {"success": False, "connected": False,
                "message": "MQTT_ENABLED não está ativo no Tesseract."}

    import paho.mqtt.client as mqtt

    started_at = time.monotonic()
    result = {"success": False, "connected": False, "subscribed": False,
              "received": False, "message": "Teste não concluído."}
    connected_event, subscribed_event, received_event = threading.Event(), threading.Event(), threading.Event()
    token = uuid.uuid4().hex
    prefix = broker_settings()["topic_prefix"] or "tesseract"
    topic = f"{prefix}/diagnostics/loopback/{token}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"tess-probe-{token[:12]}",
                         userdata={"token": token})

    username = os.environ.get("MQTT_USERNAME")
    if username:
        client.username_pw_set(username, os.environ.get("MQTT_PASSWORD"))

    def on_connect(_client, _userdata, _flags, reason_code, _properties=None):
        result["connected"] = _connected(reason_code)
        if result["connected"]:
            connected_event.set()
        else:
            result["message"] = f"Broker recusou a conexão (código {reason_code})."
            connected_event.set()

    def on_subscribe(_client, _userdata, _mid, reason_codes, _properties=None):
        result["subscribed"] = all(not getattr(code, "is_failure", False) for code in (reason_codes or []))
        if not result["subscribed"]:
            result["message"] = "Broker recusou a inscrição no tópico de diagnóstico (ACL)."
        subscribed_event.set()

    def on_message(_client, _userdata, message):
        if message.topic == topic and message.payload.decode("utf-8", errors="replace") == token:
            result["received"] = True
            received_event.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    started = False
    try:
        client.connect(broker_settings()["host"], broker_settings()["port"], keepalive=10)
        client.loop_start()
        started = True
        if not connected_event.wait(timeout):
            result["message"] = "Tempo esgotado ao conectar ao broker."
            return result
        if not result["connected"]:
            return result
        client.subscribe(topic, qos=0)
        if not subscribed_event.wait(timeout):
            result["message"] = "Conectou, mas não confirmou a inscrição de diagnóstico."
            return result
        if not result["subscribed"]:
            return result
        info = client.publish(topic, token, qos=0, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            result["message"] = f"Conectou, mas não publicou o pacote de diagnóstico (código {info.rc})."
            return result
        if not received_event.wait(timeout):
            result["message"] = "Conexão e publicação funcionaram, mas o retorno do tópico de diagnóstico não chegou. Verifique ACL/permissões de tópico."
            return result
        result.update(success=True, message="Conexão, inscrição, publicação e recebimento MQTT confirmados.",
                      topic=topic, elapsed_ms=round((time.monotonic() - started_at) * 1000, 1))
        return result
    except Exception as exc:  # surfaced as a short diagnostic, never credentials
        result["message"] = f"Falha ao testar MQTT: {str(exc)[:240]}"
        return result
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
        if started:
            try:
                client.loop_stop()
            except Exception:
                pass


def _actor_bridge_status(actor: DeviceActor) -> dict:
    identifier = actor.external_id
    heating = device_service.get_heating_telemetry(identifier)
    control = device_service.get_control_telemetry(identifier)
    source = device_service.get_source_telemetry(identifier)

    control_summary = None
    if control:
        control_summary = {key: control.get(key) for key in (
            "kind", "external_policy", "output_on", "manual_enabled", "manual_percent",
            "owner", "fault", "pending_confirmation", "last_command", "observed_at", "received_at",
        )}
    heating_summary = None
    if heating:
        heating_summary = {key: heating.get(key) for key in (
            "external_policy", "output_on", "owner", "demand_percent", "selected_percent",
            "temperature", "target", "fault", "observed_at", "received_at",
        )}
    source_summary = None
    if source:
        source_summary = {key: source.get(key) for key in (
            "participation", "armed", "output_on", "external_protection", "temperature_sensor",
            "temperature", "target", "fault", "reason", "observed_at", "received_at",
        )}
    config = actor.get_config() or {}
    mqtt = config.get("mqtt_config") or {}
    gateway_mqtt = bool(
        actor.device
        and actor.device.device_type == "gateway"
        and actor.device.protocol == "mqtt"
        and (mqtt.get("state_topic") or mqtt.get("command_topic"))
    )
    detected = bool(heating or control or source or gateway_mqtt)
    kind = (control or {}).get("kind") or (
        "source" if source else "heating" if heating else "gateway_mqtt" if gateway_mqtt else None
    )
    return {"detected": detected, "kind": kind, "heating": heating_summary,
            "control": control_summary, "source": source_summary}


def list_actor_diagnostics() -> list[dict]:
    rows = (DeviceActor.query.filter_by(is_deleted=False)
            .order_by(DeviceActor.name, DeviceActor.id).all())
    results = []
    for actor in rows:
        config = actor.get_config() or {}
        mqtt = config.get("mqtt_config") or {}
        observation = device_service.get_observation(actor.external_id)
        results.append({
            "id": actor.id,
            "device_id": actor.device_id,
            "function_id": actor.function_id,
            "external_id": actor.external_id,
            "name": actor.name,
            "device_name": actor.device.name if actor.device else None,
            "device_active": bool(actor.device and actor.device.is_active and not actor.device.is_deleted),
            "function_name": actor.function.name if actor.function else None,
            "function_label": actor.function.display_name if actor.function else None,
            "function_data_type": actor.function.data_type if actor.function else None,
            "function_min": actor.function.min_value if actor.function else None,
            "function_max": actor.function.max_value if actor.function else None,
            "actor_type": actor.actor_type,
            "is_active": actor.is_active,
            "is_risk": actor.is_risk,
            "state_topic": mqtt.get("state_topic"),
            "command_topic": mqtt.get("command_topic"),
            "observation": observation,
            "bridge": _actor_bridge_status(actor),
        })
    return results


def _validate_command_value(actor: DeviceActor, value) -> None:
    if actor.function is None:
        raise CommunicationTestError("O ator não tem uma função associada.")
    data_type = actor.function.data_type
    valid = {
        "bool": type(value) is bool,
        "int": type(value) is int,
        "float": type(value) in (int, float) and type(value) is not bool and math.isfinite(value),
        "string": isinstance(value, str),
    }.get(data_type, False)
    if not valid:
        raise CommunicationTestError(f"O valor precisa respeitar o tipo de dado da função ({data_type}).")
    if type(value) in (int, float):
        if actor.function.min_value is not None and value < actor.function.min_value:
            raise CommunicationTestError(f"Valor abaixo do mínimo ({actor.function.min_value}).")
        if actor.function.max_value is not None and value > actor.function.max_value:
            raise CommunicationTestError(f"Valor acima do máximo ({actor.function.max_value}).")


def publish_actor_test_command(actor_id: int, value, *, confirmed: bool) -> dict:
    if not confirmed:
        raise CommunicationTestError("Confirme que o comando será enviado ao equipamento real.")
    actor = DeviceActor.query.filter_by(id=actor_id, is_deleted=False).first()
    if not actor or not actor.is_active or not actor.device or not actor.device.is_active or actor.device.is_deleted:
        raise CommunicationTestError("Ator/dispositivo ausente ou inativo.")
    if actor.actor_type != "actuator":
        raise CommunicationTestError("Envio de comando está disponível somente para atores do tipo Atuador.")
    if actor.is_risk:
        raise CommunicationTestError("Atuador marcado como risco não aceita comando bruto pelo painel. Use os controles protegidos do Mash Control.")
    config = actor.get_config() or {}
    runtime = config.get("runtime") or {}
    if any(runtime.get(key) for key in ("bridge_control", "bridge_heating", "bridge_source")):
        raise CommunicationTestError("Ator Bridge usa contrato de controle protegido. Use os controles do Mash Control.")
    mqtt = config.get("mqtt_config") or {}
    topic = mqtt.get("command_topic")
    if not topic:
        raise CommunicationTestError("Este ator não tem command_topic configurado.")
    if not mqtt_client_service.is_connected():
        raise CommunicationTestError("Tesseract não está conectado ao broker MQTT configurado.")
    _validate_command_value(actor, value)
    qos = mqtt.get("qos", 0)
    if type(qos) is not int or qos not in (0, 1, 2):
        qos = 0
    if not mqtt_client_service.publish(topic, value, qos=qos, retain=False):
        raise CommunicationTestError("A publicação não foi aceita pelo cliente MQTT.")
    return {"success": True, "topic": topic, "qos": qos,
            "message": "Comando enviado ao broker. Isso confirma a publicação, não a execução física pelo dispositivo."}


def publish_mqtt_test_message(topic: str, payload: str, *, payload_format: str = "json",
                              qos: int = 0, retain: bool = False, confirmed: bool = False) -> dict:
    """Publica em tópico MQTT livre, com ou sem ator associado, para diagnóstico manual."""
    if confirmed is not True:
        raise CommunicationTestError("Confirme que a publicação pode alterar dados ou acionar um equipamento real.")
    if not isinstance(topic, str):
        raise CommunicationTestError("Informe o tópico MQTT de destino.")
    topic = topic.strip().lstrip("/")
    try:
        topic_size = len(topic.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise CommunicationTestError("O tópico contém caracteres inválidos.") from exc
    if not topic or topic_size > 1024 or any(char in topic for char in ("+", "#", "\x00")):
        raise CommunicationTestError("Tópico vazio, longo ou inválido. Publicações não aceitam curingas + ou #.")
    if not isinstance(payload, str):
        raise CommunicationTestError("O payload precisa ser enviado como texto.")
    try:
        payload_size = len(payload.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise CommunicationTestError("O payload contém caracteres inválidos.") from exc
    if payload_size > MQTT_TEST_MAX_PAYLOAD:
        raise CommunicationTestError("Payload excede o limite de 32 KB.")
    if not isinstance(payload_format, str) or payload_format not in {"json", "text"}:
        raise CommunicationTestError("Formato de payload deve ser JSON ou texto.")
    if payload_format == "json":
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CommunicationTestError("O payload informado não é um JSON válido.") from exc
    if type(qos) is not int or qos not in (0, 1, 2):
        raise CommunicationTestError("QoS precisa ser 0, 1 ou 2.")
    if type(retain) is not bool:
        raise CommunicationTestError("Retain precisa ser verdadeiro ou falso.")
    if not mqtt_client_service.is_connected():
        raise CommunicationTestError("Tesseract não está conectado ao broker MQTT configurado.")
    if not mqtt_client_service.publish(topic, payload, qos=qos, retain=retain):
        raise CommunicationTestError("O cliente MQTT não aceitou a publicação.")

    prefix = broker_settings()["topic_prefix"]
    full_topic = f"{prefix}/{topic}" if prefix else topic
    return {
        "success": True,
        "topic": topic,
        "full_topic": full_topic,
        "qos": qos,
        "retain": retain,
        "message": "Publicação aceita pelo cliente MQTT. Confira o recebimento no broker ou device; isso não confirma execução física.",
    }


def send_bridge_control(actor_id: int, action: str, value=None, *, confirmed: bool) -> dict:
    if not confirmed:
        raise CommunicationTestError("Confirme que a ação pode operar o equipamento real.")
    actor = DeviceActor.query.filter_by(id=actor_id, is_deleted=False).first()
    if not actor or not actor.is_active or not actor.device or not actor.device.is_active or actor.device.is_deleted:
        raise CommunicationTestError("Ator/dispositivo ausente ou inativo.")
    try:
        request_id = device_service.send_device_control(actor.external_id, action, value)
    except (ValueError, TypeError) as exc:
        raise CommunicationTestError(str(exc)) from exc
    return {"success": True, "request_id": request_id,
            "message": "Comando validado e publicado. A confirmação do Bridge aparece na telemetria do ator."}


def _validate_rest_target(url: str):
    if not isinstance(url, str) or len(url) > 2048:
        raise CommunicationTestError("Informe uma URL de até 2.048 caracteres.")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise CommunicationTestError("URL ou porta inválida.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CommunicationTestError("Use uma URL http:// ou https:// para um dispositivo da rede local.")
    if parsed.username or parsed.password or parsed.fragment:
        raise CommunicationTestError("Não inclua usuário/senha na URL nem fragmentos (#). Use cabeçalho Authorization.")
    hostname = parsed.hostname
    if hostname.casefold() == "localhost":
        return parsed, port
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError as exc:
        raise CommunicationTestError("Por segurança, informe o IP numérico do dispositivo (IPv4/IPv6); nomes DNS não são aceitos.") from exc
    allowed = address.is_loopback or (
        isinstance(address, ipaddress.IPv4Address) and any(address in net for net in _PRIVATE_V4)
    ) or (isinstance(address, ipaddress.IPv6Address) and any(address in net for net in _PRIVATE_V6))
    if not allowed or address.is_link_local or address.is_multicast or address.is_unspecified:
        raise CommunicationTestError("O painel só pode chamar IPs locais/privados ou localhost; IP público, link-local e multicast são bloqueados.")
    return parsed, port


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run_rest_request(*, url: str, method: str, headers_json: str = "{}", body: str = "") -> dict:
    method = (method or "GET").upper()
    if method not in REST_METHODS:
        raise CommunicationTestError("Método HTTP não permitido.")
    parsed, _port = _validate_rest_target(url)
    try:
        headers = json.loads(headers_json or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        raise CommunicationTestError("Cabeçalhos precisam ser um objeto JSON válido.") from exc
    if not isinstance(headers, dict) or len(headers) > 24:
        raise CommunicationTestError("Cabeçalhos precisam ser um objeto JSON com até 24 itens.")
    clean_headers = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
            raise CommunicationTestError("Cada cabeçalho precisa ter nome texto e valor simples.")
        normalized = key.strip()
        if not normalized or "\r" in normalized or "\n" in normalized or normalized.casefold() in _BLOCKED_HEADERS:
            raise CommunicationTestError(f"Cabeçalho não permitido: {normalized[:80]}.")
        text_value = str(value)
        if "\r" in text_value or "\n" in text_value or len(text_value) > 4096:
            raise CommunicationTestError(f"Valor inválido no cabeçalho {normalized}.")
        clean_headers[normalized] = text_value

    data = None
    if body and not isinstance(body, str):
        raise CommunicationTestError("O corpo HTTP precisa ser texto JSON.")
    if method in {"POST", "PUT", "PATCH", "DELETE"} and body:
        if len(body.encode("utf-8")) > REST_MAX_BODY:
            raise CommunicationTestError("Corpo excede o limite de 32 KB.")
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            raise CommunicationTestError("O corpo precisa ser JSON válido.") from exc
        data = body.encode("utf-8")
        clean_headers.setdefault("Content-Type", "application/json")
    if not clean_headers.get("Accept"):
        clean_headers["Accept"] = "application/json, text/plain, */*"

    request = urllib.request.Request(url, data=data, headers=clean_headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    started = time.monotonic()
    status, response_headers, response_body = 0, {}, b""
    try:
        with opener.open(request, timeout=REST_TIMEOUT_SECONDS) as response:
            status = response.status
            response_headers = dict(response.headers.items())
            response_body = response.read(REST_MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items()) if exc.headers else {}
        response_body = exc.read(REST_MAX_RESPONSE + 1)
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CommunicationTestError(f"Falha REST: {str(reason)[:240]}") from exc
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    truncated = len(response_body) > REST_MAX_RESPONSE
    response_body = response_body[:REST_MAX_RESPONSE]
    charset = "utf-8"
    content_type = next((v for k, v in response_headers.items() if k.casefold() == "content-type"), "")
    if "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip(' "\'')[:40] or "utf-8"
    try:
        text_body = response_body.decode(charset, errors="replace")
    except LookupError:
        text_body = response_body.decode("utf-8", errors="replace")
    try:
        parsed_json = json.loads(text_body) if text_body else None
    except json.JSONDecodeError:
        parsed_json = None
    return {"success": 200 <= status < 400, "status": status,
            "elapsed_ms": elapsed_ms, "headers": response_headers,
            "body": json.dumps(parsed_json, ensure_ascii=False, indent=2) if parsed_json is not None else text_body,
            "truncated": truncated, "redirect_blocked": 300 <= status < 400,
            "url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}"}
