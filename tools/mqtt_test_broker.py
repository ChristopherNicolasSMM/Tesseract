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
import signal
import threading
from datetime import datetime, timezone
from typing import Any

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
    input,textarea{width:min(100%,700px);box-sizing:border-box}textarea{height:100px;font-family:ui-monospace,monospace}button{background:#1f4c9a;color:white;border:0;cursor:pointer;margin-top:10px}
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
document.querySelector('#publish').onclick=async()=>{
  const feedback=document.querySelector('#feedback'); feedback.textContent='Publicando…';
  try { const r=await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:document.querySelector('#topic').value,payload:document.querySelector('#payload').value,qos:Number(document.querySelector('#qos').value)})}); const d=await r.json(); feedback.textContent=d.success?'Mensagem enviada.':(d.error||'Falha ao publicar.'); await refresh(); }
  catch(e){feedback.textContent='Erro: '+e.message;}
};
refresh(); setInterval(refresh,2000);
</script>
</body></html>"""

app = Flask(__name__)
SETTINGS = {"mqtt_host": "127.0.0.1", "mqtt_port": 1883, "web_host": "127.0.0.1", "web_port": 5055}


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
        if int(reason_code) == 0:
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
    args = parser.parse_args()
    if not 1 <= args.mqtt_port <= 65535 or not 1 <= args.web_port <= 65535:
        parser.error("as portas devem estar entre 1 e 65535")
    SETTINGS.update(mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port, web_host=args.web_host, web_port=args.web_port)

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
    LOG.info("Tesseract local: MQTT_BROKER_HOST=127.0.0.1 MQTT_BROKER_PORT=%s MQTT_ENABLED=true", args.mqtt_port)
    try:
        app.run(host=args.web_host, port=args.web_port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        if MONITOR is not None:
            MONITOR.disconnect()
            MONITOR.loop_stop()
        if BROKER_LOOP and BROKER_INSTANCE:
            BROKER_LOOP.call_soon_threadsafe(BROKER_LOOP.stop)
            thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
