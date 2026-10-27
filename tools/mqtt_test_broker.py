#!/usr/bin/env python3
"""Broker MQTT local de teste com painel HTTP/Flask.

Uso:
    pip install amqtt==0.12.1
    python tools/mqtt_test_broker.py

O broker escuta em 127.0.0.1:1883 e o painel em http://127.0.0.1:5055.
Altere portas/hosts pelas opções --mqtt-host, --mqtt-port, --web-host e
--web-port. O broker aceita conexões anônimas e é destinado somente a testes
locais; não o exponha à internet ou a redes não confiáveis.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from amqtt.broker import Broker
from flask import Flask, jsonify, render_template_string, request
import paho.mqtt.client as mqtt


LOG = logging.getLogger("mqtt_test_broker")
MESSAGES: list[dict[str, Any]] = []
MESSAGES_LOCK = threading.Lock()
MAX_MESSAGES = 500
BROKER_READY = threading.Event()
BROKER_ERROR: list[BaseException] = []
BROKER_LOOP: asyncio.AbstractEventLoop | None = None
BROKER_INSTANCE: Broker | None = None
MONITOR: mqtt.Client | None = None
MONITOR_CONNECTED = threading.Event()
BRIDGE_SIMULATOR = None
BRIDGE_SIMULATOR_LOCK = threading.Lock()

PAGE = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Broker MQTT de teste</title>
  <style>
    body{font:15px system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;color:#172033;background:#f4f6fa}
    h1{margin-bottom:4px}.muted{color:#637083}.card{background:white;border:1px solid #dce2eb;border-radius:10px;padding:16px;margin:16px 0}
    code{background:#eef1f6;padding:2px 5px;border-radius:4px}.status{font-weight:700}.up{color:#147d43}.down{color:#b42318}
    label{display:block;font-weight:600;margin:10px 0 4px}input,textarea,select,button{font:inherit;padding:9px;border:1px solid #cbd3df;border-radius:6px}
    input,textarea,select{width:min(100%,700px);box-sizing:border-box}textarea{height:100px;font-family:ui-monospace,monospace}button{background:#1f4c9a;color:white;border:0;cursor:pointer;margin:10px 8px 0 0}button:disabled{opacity:.55;cursor:not-allowed}.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
    table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;border-bottom:1px solid #e4e8ef;padding:8px;vertical-align:top}td.payload{white-space:pre-wrap;overflow-wrap:anywhere;font-family:ui-monospace,monospace}
    .scroll{overflow:auto;max-height:520px}#feedback{margin-left:10px}
  </style>
</head>
<body>
  <h1>Broker MQTT de teste</h1>
  <p class="muted">Broker local para validar conexões e mensagens do Tesseract e de devices simulados.</p>
  <section class="card">
    <div>MQTT: <code id="mqtt-address">carregando…</code> · <span id="mqtt-status" class="status">iniciando</span></div>
    <div>Painel Flask: <code id="web-address"></code> · Monitor de mensagens: <span id="monitor-status">iniciando</span></div>
    <p class="muted">O monitor assina <code>#</code>; mensagens MQTT publicadas no broker aparecem abaixo.</p>
  </section>
  <section class="card">
    <h2>Simulador Tesseract Device Bridge · contrato v1</h2>
    <p class="muted">Publica telemetria a cada segundo, assina o command_topic e responde com ACK em <code>last_command</code>. Use o mesmo device_id e os mesmos tópicos relativos cadastrados no ator do Tesseract.</p>
    <div class="row">
      <div><label for="bridge-device-id">Device ID (nome da função no Tesseract)</label><input id="bridge-device-id" value="mash_heater"></div>
      <div><label for="bridge-command-topic">command_topic</label><input id="bridge-command-topic" value="actuators/mash_heater/set"></div>
      <div><label for="bridge-state-topic">state_topic</label><input id="bridge-state-topic" value="sensors/mash_heater/state"></div>
      <div><label for="bridge-kind">Tipo de controle</label><select id="bridge-kind"><option value="power">Potência / aquecimento</option><option value="pump">Bomba</option></select></div>
      <div><label for="bridge-policy">Política externa</label><select id="bridge-policy"><option value="manual_override">manual_override</option><option value="local_only">local_only</option></select></div>
    </div>
    <label><input id="bridge-pending-confirmation" type="checkbox" style="width:auto"> Iniciar bomba com confirmação pendente (para testar pump_confirm / pump_decline)</label>
    <div><button id="bridge-start">Iniciar simulador Bridge</button><button id="bridge-stop" disabled>Parar simulador</button><span id="bridge-feedback" role="status"></span></div>
    <div class="muted" id="bridge-status">Simulador parado. Informe tópicos relativos, sem repetir o prefixo.</div>
  </section>
  <section class="card">
    <h2>Publicar mensagem de teste</h2>
    <label for="topic">Tópico</label><input id="topic" value="tesseract/device/test/state">
    <label for="payload">Payload JSON ou texto</label><textarea id="payload">{"value": 21.5, "unit": "C"}</textarea>
    <label for="qos">QoS</label><select id="qos"><option>0</option><option>1</option><option>2</option></select>
    <div><button id="publish">Publicar no broker</button><span id="feedback" role="status"></span></div>
  </section>
  <section class="card">
    <h2>Mensagens recentes</h2><button id="refresh">Atualizar</button>
    <div class="scroll"><table><thead><tr><th>Horário UTC</th><th>Tópico</th><th>QoS</th><th>Payload</th></tr></thead><tbody id="messages"></tbody></table></div>
  </section>
<script>
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function refresh(){
  const [s,m] = await Promise.all([fetch('/api/status').then(r=>r.json()),fetch('/api/messages?limit=200').then(r=>r.json())]);
  document.querySelector('#mqtt-address').textContent = `${s.mqtt.host}:${s.mqtt.port}`;
  document.querySelector('#web-address').textContent = `${location.hostname}:${s.web.port}`;
  const state = document.querySelector('#mqtt-status'); state.textContent = s.broker_ready ? 'Broker ativo' : 'Broker parado'; state.className = `status ${s.broker_ready?'up':'down'}`;
  document.querySelector('#monitor-status').textContent = s.monitor_connected ? 'conectado' : 'reconectando';
  document.querySelector('#messages').innerHTML = m.messages.map(x=>`<tr><td>${esc(x.time)}</td><td>${esc(x.topic)}</td><td>${esc(x.qos)}</td><td class="payload">${esc(x.payload)}</td></tr>`).join('') || '<tr><td colspan="4">Nenhuma mensagem recebida ainda.</td></tr>';
}
document.querySelector('#refresh').onclick=refresh;
async function refreshBridge(){
  const s=await fetch('/api/bridge-simulator/status').then(r=>r.json()); const sim=s.simulator;
  document.querySelector('#bridge-status').textContent=sim.running?`Ativo · ${sim.device_id} · ${sim.kind} · MQTT ${sim.connected?'conectado':'conectando'} · state=${sim.state_topic} · command=${sim.command_topic}`:'Simulador parado. Informe tópicos relativos, sem repetir o prefixo.';
  document.querySelector('#bridge-start').disabled=sim.running; document.querySelector('#bridge-stop').disabled=!sim.running;
}
document.querySelector('#bridge-start').onclick=async()=>{
  const feedback=document.querySelector('#bridge-feedback'); feedback.textContent='Iniciando…';
  const r=await fetch('/api/bridge-simulator/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:document.querySelector('#bridge-device-id').value,command_topic:document.querySelector('#bridge-command-topic').value,state_topic:document.querySelector('#bridge-state-topic').value,kind:document.querySelector('#bridge-kind').value,external_policy:document.querySelector('#bridge-policy').value,pending_confirmation:document.querySelector('#bridge-pending-confirmation').checked})});
  const d=await r.json(); feedback.textContent=d.success?'Simulador iniciado.':(d.error||'Falha ao iniciar.'); await refreshBridge();
};
document.querySelector('#bridge-stop').onclick=async()=>{await fetch('/api/bridge-simulator/stop',{method:'POST'}); await refreshBridge();};
document.querySelector('#publish').onclick=async()=>{
  const feedback=document.querySelector('#feedback'); feedback.textContent='Publicando…';
  try { const r=await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:document.querySelector('#topic').value,payload:document.querySelector('#payload').value,qos:Number(document.querySelector('#qos').value)})}); const d=await r.json(); feedback.textContent=d.success?'Mensagem enviada.':(d.error||'Falha ao publicar.'); await refresh(); }
  catch(e){feedback.textContent='Erro: '+e.message;}
};
refresh(); refreshBridge(); setInterval(refresh,2000); setInterval(refreshBridge,1000);
</script>
</body></html>"""

app = Flask(__name__)
SETTINGS = {"mqtt_host": "127.0.0.1", "mqtt_port": 1883, "web_host": "127.0.0.1", "web_port": 5055, "topic_prefix": "tesseract"}


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/health")
@app.get("/api/status")
def status():
    with MESSAGES_LOCK:
        count = len(MESSAGES)
    return jsonify({
        "broker_ready": BROKER_READY.is_set() and not BROKER_ERROR,
        "mqtt": {"host": SETTINGS["mqtt_host"], "port": SETTINGS["mqtt_port"]},
        "topic_prefix": SETTINGS["topic_prefix"],
        "web": {"host": SETTINGS["web_host"], "port": SETTINGS["web_port"]},
        "monitor_connected": MONITOR_CONNECTED.is_set(),
        "messages_buffered": count,
    })


@app.get("/api/messages")
def messages():
    try:
        limit = max(1, min(int(request.args.get("limit", "100")), MAX_MESSAGES))
    except ValueError:
        return jsonify(error="limit precisa ser número inteiro."), 400
    with MESSAGES_LOCK:
        result = list(reversed(MESSAGES[-limit:]))
    return jsonify(messages=result)


@app.post("/api/publish")
def publish():
    if not MONITOR or not MONITOR_CONNECTED.is_set():
        return jsonify(success=False, error="O cliente de monitoramento ainda não conectou ao broker."), 503
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, error="Envie um objeto JSON com topic e payload."), 400
    topic = str(data.get("topic", "")).strip()
    if not topic or "+" in topic or "#" in topic:
        return jsonify(success=False, error="Informe um tópico de publicação sem curingas MQTT."), 400
    try:
        qos = int(data.get("qos", 0))
    except (TypeError, ValueError):
        qos = -1
    if qos not in (0, 1, 2):
        return jsonify(success=False, error="QoS deve ser 0, 1 ou 2."), 400
    payload = data.get("payload", "")
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)
    info = MONITOR.publish(topic, payload, qos=qos, retain=False)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        return jsonify(success=False, error=f"Paho recusou a publicação (rc={info.rc})."), 502
    return jsonify(success=True, topic=topic, qos=qos, message="Publicado no broker; isso confirma transporte MQTT, não ação física do device."), 202


@app.get("/api/bridge-simulator/status")
def bridge_simulator_status():
    simulator = BRIDGE_SIMULATOR
    return jsonify(simulator={"running": bool(simulator and simulator.running),
                              **(simulator.status() if simulator else {})})


@app.post("/api/bridge-simulator/start")
def bridge_simulator_start():
    global BRIDGE_SIMULATOR
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, error="Configuração JSON inválida."), 400
    try:
        config = {
            "device_id": str(data.get("device_id", "")).strip(),
            "command_topic": str(data.get("command_topic", "")).strip(),
            "state_topic": str(data.get("state_topic", "")).strip(),
            "kind": data.get("kind", "power"),
            "external_policy": data.get("external_policy", "manual_override"),
            "pending_confirmation": data.get("pending_confirmation") is True,
        }
        for field in ("device_id", "command_topic", "state_topic"):
            value = config[field]
            if not value or len(value.encode("utf-8")) > 128 or any(c in value for c in ("+", "#", "\x00")):
                raise ValueError(f"{field} vazio ou inválido.")
        if config["kind"] not in {"power", "pump"}:
            raise ValueError("kind precisa ser power ou pump.")
        if config["external_policy"] not in {"manual_override", "local_only"}:
            raise ValueError("external_policy precisa ser manual_override ou local_only.")
        with BRIDGE_SIMULATOR_LOCK:
            if BRIDGE_SIMULATOR and BRIDGE_SIMULATOR.running:
                BRIDGE_SIMULATOR.stop()
            BRIDGE_SIMULATOR = BridgeSimulator(config)
            BRIDGE_SIMULATOR.start()
        return jsonify(success=True, simulator=BRIDGE_SIMULATOR.status()), 202
    except (ValueError, OSError) as exc:
        return jsonify(success=False, error=str(exc)), 400


@app.post("/api/bridge-simulator/stop")
def bridge_simulator_stop():
    global BRIDGE_SIMULATOR
    with BRIDGE_SIMULATOR_LOCK:
        if BRIDGE_SIMULATOR:
            BRIDGE_SIMULATOR.stop()
            BRIDGE_SIMULATOR = None
    return jsonify(success=True)


def _full_topic(topic: str) -> str:
    prefix = str(SETTINGS.get("topic_prefix", "")).strip("/")
    topic = topic.strip("/")
    return f"{prefix}/{topic}" if prefix else topic


class BridgeSimulator:
    """Minimal simulated device implementing the Device Manager control-v1 MQTT contract."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.command_topic = _full_topic(config["command_topic"])
        self.state_topic = _full_topic(config["state_topic"])
        self.boot_id = uuid4().hex
        self.sequence = 0
        self.output_on = False
        self.manual_enabled = False
        self.manual_percent = 0.0
        self.owner = "idle"
        self.pending_confirmation = bool(config.get("pending_confirmation"))
        self.last_command = None
        self.running = False
        self.connected = threading.Event()
        self.stopping = threading.Event()
        self.lock = threading.RLock()
        self.publisher_thread = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"tess-sim-bridge-{uuid4().hex[:10]}",
                                  protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)

    def start(self) -> None:
        self.client.connect(SETTINGS["mqtt_host"], SETTINGS["mqtt_port"], keepalive=30)
        self.client.loop_start()
        self.running = True
        self.publisher_thread = threading.Thread(target=self._publish_loop, name="bridge-simulator", daemon=True)
        self.publisher_thread.start()

    def stop(self) -> None:
        self.running = False
        self.stopping.set()
        try:
            self.client.disconnect()
            self.client.loop_stop()
        finally:
            if self.publisher_thread and self.publisher_thread is not threading.current_thread():
                self.publisher_thread.join(timeout=2)

    def status(self) -> dict[str, Any]:
        return {"connected": self.connected.is_set(), "device_id": self.config["device_id"],
                "kind": self.config["kind"], "external_policy": self.config["external_policy"],
                "command_topic": self.config["command_topic"], "state_topic": self.config["state_topic"],
                "full_command_topic": self.command_topic, "full_state_topic": self.state_topic}

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None):
        value = getattr(reason_code, "value", reason_code)
        try:
            ok = int(value) == 0
        except (TypeError, ValueError):
            ok = not getattr(reason_code, "is_failure", True)
        if not ok:
            self.connected.clear()
            LOG.error("Broker recusou o simulador Bridge: %s", reason_code)
            return
        self.connected.set()
        client.subscribe(self.command_topic, qos=1)
        LOG.info("Bridge simulado %s ouvindo %s", self.config["device_id"], self.command_topic)
        self._publish_state()

    def _on_disconnect(self, _client, _userdata, _flags, _reason_code, _properties=None):
        self.connected.clear()

    def _on_message(self, _client, _userdata, message):
        try:
            envelope = json.loads(message.payload.decode("utf-8"))
            command = envelope.get("device_control") if isinstance(envelope, dict) else None
            if not isinstance(command, dict):
                raise ValueError("Payload sem device_control v1.")
            self._apply_command(command)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            LOG.warning("Comando inválido recebido pelo Bridge simulado: %s", exc)

    def _apply_command(self, command: dict[str, Any]) -> None:
        action = command.get("action")
        request_id = command.get("request_id")
        message = "Comando aplicado pela simulação."
        success = True
        with self.lock:
            try:
                if command.get("version") != 1 or command.get("boot_id") != self.boot_id:
                    raise ValueError("Versão ou boot_id não corresponde ao Bridge simulado.")
                if not isinstance(request_id, str) or not request_id:
                    raise ValueError("request_id ausente.")
                issued = command.get("issued_at")
                issued_at = datetime.fromisoformat(issued.replace("Z", "+00:00")) if isinstance(issued, str) else None
                if not issued_at or issued_at.tzinfo is None:
                    raise ValueError("issued_at precisa ter fuso UTC.")
                age = (datetime.now(timezone.utc) - issued_at.astimezone(timezone.utc)).total_seconds()
                if not -2 <= age <= 5:
                    raise ValueError("Comando fora da janela de 5 segundos.")
                if self.config["external_policy"] == "local_only" and action != "power_off":
                    raise ValueError("Política local_only: apenas power_off remoto é permitido.")
                kind = self.config["kind"]
                value = command.get("value")
                if kind == "power":
                    if action == "power_prepare":
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                            raise ValueError("Potência precisa estar entre 0 e 100%.")
                        self.manual_percent = float(value)
                        if self.manual_enabled:
                            self.output_on = self.manual_percent > 0
                    elif action == "power_enable":
                        self.manual_enabled = True; self.output_on = self.manual_percent > 0; self.owner = "remote_manual"
                    elif action == "power_release":
                        self.manual_enabled = False; self.output_on = False; self.owner = "idle"
                    elif action == "power_off":
                        self.manual_enabled = True; self.manual_percent = 0.0; self.output_on = False; self.owner = "remote_manual"
                    else:
                        raise ValueError("Ação incompatível com kind=power.")
                else:
                    if action == "pump_set" and type(value) is bool:
                        self.manual_enabled = True; self.output_on = value; self.owner = "remote_manual"
                    elif action == "pump_release":
                        self.manual_enabled = False; self.output_on = False; self.owner = "idle"
                    elif action in {"pump_confirm", "pump_decline"} and self.pending_confirmation:
                        self.output_on = action == "pump_confirm"; self.pending_confirmation = False; self.owner = "remote_manual" if self.output_on else "idle"
                    else:
                        raise ValueError("Ação incompatível ou confirmação de bomba inexistente.")
            except (ValueError, TypeError) as exc:
                success = False; message = str(exc)
            self.last_command = {"request_id": str(request_id or "invalid"), "action": str(action or "unknown"),
                                 "status": "applied" if success else "rejected", "message": message}
        LOG.info("Bridge simulado %s: %s (%s)", self.config["device_id"], action, "applied" if success else "rejected")
        self._publish_state()

    def _publish_state(self) -> None:
        if not self.connected.is_set():
            return
        with self.lock:
            self.sequence += 1
            observed_at = datetime.now(timezone.utc).isoformat()
            value = self.output_on if self.config["kind"] == "pump" else (self.manual_percent if self.manual_enabled else 0.0)
            control = {"version": 1, "device_id": self.config["device_id"], "boot_id": self.boot_id,
                       "sequence": self.sequence, "observed_at": observed_at, "backend": "simulated",
                       "kind": self.config["kind"], "external_policy": self.config["external_policy"],
                       "output_on": self.output_on, "manual_enabled": self.manual_enabled,
                       "manual_percent": self.manual_percent, "owner": self.owner, "fault": None,
                       "pending_confirmation": self.pending_confirmation, "last_command": self.last_command}
            payload = json.dumps({"value": value, "control": control}, ensure_ascii=False)
        info = self.client.publish(self.state_topic, payload, qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            LOG.warning("Telemetria Bridge simulado não aceita pelo cliente MQTT: rc=%s", info.rc)

    def _publish_loop(self) -> None:
        while not self.stopping.wait(1.0):
            self._publish_state()


async def _run_broker() -> None:
    global BROKER_INSTANCE
    bind = f"{SETTINGS['mqtt_host']}:{SETTINGS['mqtt_port']}"
    config = {
        "listeners": {"default": {"type": "tcp", "bind": bind}},
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True},
            "amqtt.plugins.logging_amqtt.EventLoggerPlugin": {},
        },
    }
    BROKER_INSTANCE = Broker(config)
    await BROKER_INSTANCE.start()
    BROKER_READY.set()
    LOG.info("Broker MQTT escutando em %s", bind)


def _broker_thread() -> None:
    global BROKER_LOOP
    BROKER_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(BROKER_LOOP)
    try:
        BROKER_LOOP.run_until_complete(_run_broker())
        BROKER_LOOP.run_forever()
    except BaseException as exc:
        BROKER_ERROR.append(exc)
        BROKER_READY.set()
        LOG.exception("Não foi possível iniciar o broker MQTT: %s", exc)
    finally:
        if BROKER_INSTANCE is not None:
            try:
                BROKER_LOOP.run_until_complete(BROKER_INSTANCE.shutdown())
            except Exception:
                LOG.exception("Falha ao encerrar o broker MQTT.")
        BROKER_LOOP.close()


def _start_monitor() -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="python-test-broker-monitor",
        protocol=mqtt.MQTTv311,
    )

    def on_connect(client, _userdata, _flags, reason_code, _properties=None):
        # Paho 2.x passa mqtt.ReasonCode, cujo valor numérico fica em .value.
        # Converter diretamente com int(reason_code) gera TypeError.
        code_value = getattr(reason_code, "value", reason_code)
        try:
            connected = int(code_value) == 0
        except (TypeError, ValueError):
            connected = not getattr(reason_code, "is_failure", True)
        if connected:
            MONITOR_CONNECTED.set()
            client.subscribe("#", qos=0)
            LOG.info("Monitor conectado e inscrito em todos os tópicos (#).")
        else:
            MONITOR_CONNECTED.clear()
            LOG.warning("O broker recusou o monitor: %s", reason_code)

    def on_disconnect(_client, _userdata, _flags, _reason_code, _properties=None):
        MONITOR_CONNECTED.clear()

    def on_message(_client, _userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = f"<payload binário: {len(msg.payload)} bytes>"
        entry = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "topic": msg.topic,
            "qos": msg.qos,
            "retain": bool(msg.retain),
            "payload": payload,
        }
        with MESSAGES_LOCK:
            MESSAGES.append(entry)
            del MESSAGES[:-MAX_MESSAGES]
        LOG.info("MQTT %s qos=%s payload=%s", msg.topic, msg.qos, payload[:300])

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    client.connect(SETTINGS["mqtt_host"], SETTINGS["mqtt_port"], keepalive=30)
    client.loop_start()
    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="Broker MQTT local de teste com painel Flask.")
    parser.add_argument("--mqtt-host", default="127.0.0.1", help="Interface para escutar MQTT (padrão: 127.0.0.1).")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="Porta MQTT (padrão: 1883).")
    parser.add_argument("--web-host", default="127.0.0.1", help="Interface do painel Flask (padrão: 127.0.0.1).")
    parser.add_argument("--web-port", type=int, default=5055, help="Porta do painel Flask (padrão: 5055).")
    parser.add_argument("--topic-prefix", default="tesseract", help="Prefixo MQTT usado pelo Tesseract (padrão: tesseract).")
    args = parser.parse_args()
    if not 1 <= args.mqtt_port <= 65535 or not 1 <= args.web_port <= 65535:
        parser.error("as portas devem estar entre 1 e 65535")
    SETTINGS.update(mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port, web_host=args.web_host,
                    web_port=args.web_port, topic_prefix=args.topic_prefix.strip("/"))

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    thread = threading.Thread(target=_broker_thread, name="mqtt-broker", daemon=True)
    thread.start()
    if not BROKER_READY.wait(timeout=10):
        LOG.error("Tempo esgotado ao iniciar o broker MQTT.")
        return 1
    if BROKER_ERROR:
        LOG.error("Verifique se a porta %s já está ocupada e tente outra com --mqtt-port.", args.mqtt_port)
        return 1

    global MONITOR
    try:
        MONITOR = _start_monitor()
    except OSError as exc:
        LOG.exception("O broker iniciou, mas o monitor MQTT falhou: %s", exc)

    LOG.info("Painel Flask em http://%s:%s", args.web_host, args.web_port)
    LOG.info("Tesseract local: MQTT_BROKER_HOST=127.0.0.1 MQTT_BROKER_PORT=%s MQTT_TOPIC_PREFIX=%s MQTT_ENABLED=true", args.mqtt_port, SETTINGS["topic_prefix"])
    try:
        app.run(host=args.web_host, port=args.web_port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        if BRIDGE_SIMULATOR:
            BRIDGE_SIMULATOR.stop()
        if MONITOR is not None:
            MONITOR.disconnect()
            MONITOR.loop_stop()
        if BROKER_LOOP and BROKER_INSTANCE:
            BROKER_LOOP.call_soon_threadsafe(BROKER_LOOP.stop)
            thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
