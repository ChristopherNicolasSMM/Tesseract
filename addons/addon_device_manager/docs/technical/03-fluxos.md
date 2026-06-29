# 03 — Fluxos (`addon_device_manager`)

> Diagramas reaproveitados de `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`
> (seção 5), já validados em produção — reproduzidos aqui no formato
> exigido pela skill 04 para a documentação do próprio Addon.

## Fluxo 1 — Leitura de sensor (caminho feliz)

```mermaid
sequenceDiagram
    participant HW as Hardware (Pi/ESP32)
    participant Broker as Broker MQTT
    participant MQTT as mqtt_client_service._on_message
    participant Svc as device_service.update_from_mqtt
    participant DB as DeviceActor.config_json["runtime"]

    HW->>Broker: publish state_topic (valor)
    Broker->>MQTT: mensagem roteada (assinatura ativa)
    MQTT->>MQTT: resolve DeviceActor pelo state_topic
    MQTT->>Svc: update_from_mqtt(actor, valor)
    Svc->>Svc: valida faixa (DeviceFunction.min_value/max_value)
    alt fora da faixa
        Svc->>Svc: loga erro global (mas registra o valor mesmo assim)
    else dentro da faixa
        Svc->>Svc: loga evento de rotina (integration_logger, local)
    end
    Svc->>DB: atualiza last_value, last_seen_at
    Svc->>Svc: dispara on_change (por actor) + publica no EventBus do Core (device_manager.actor.value_changed)
```

## Fluxo 2 — Comando de atuador (caminho feliz)

```mermaid
sequenceDiagram
    participant Cliente as Addon dependente (ex: mash_control)
    participant Svc as device_service.set_value
    participant MQTT as mqtt_client_service.publish
    participant Broker as Broker MQTT
    participant HW as Hardware (Pi/ESP32)

    Cliente->>Svc: set_value(external_id_ou_name, valor)
    Svc->>Svc: valida faixa — REJEITA se fora (retorna False)
    Svc->>Svc: atualiza config_json["runtime"] (cache) + log de rotina local
    Svc->>Svc: dispara on_change (por actor) + publica no EventBus (device_manager.actor.value_changed)
    Svc->>MQTT: publish(command_topic, valor) — só se mqtt_config presente e cliente conectado
    MQTT->>Broker: publish
    Broker->>HW: mensagem roteada
```

## Fluxo 3 — Fail-safe (LWT agregado) — conexão do Tesseract cai

```mermaid
sequenceDiagram
    participant Tess as addon_device_manager
    participant Broker as Broker MQTT
    participant Bridge as tesseract-device-bridge (Pi)

    Tess->>Broker: connect() + will_set(status_topic, payload_agregado)
    Note over Tess,Broker: payload = {"status": "offline", "failsafe_actuators": [{command_topic, failsafe_value}, ...]}
    Bridge->>Broker: subscribe(status_topic)
    Tess--xBroker: conexão cai (crash/rede)
    Broker->>Broker: detecta keepalive expirado
    Broker->>Bridge: publica o payload do LWT (status="offline")
    Bridge->>Bridge: aplica failsafe_value localmente em cada item, sem round-trip de rede
```

> Correção de protocolo (registrada na Fase D): MQTT permite só **um**
> LWT por conexão de cliente — por isso o payload é agregado (lista de
> atuadores de risco), não um LWT por atuador.

## Fluxo 4 — Motor de automação reativo (Fase E)

```mermaid
sequenceDiagram
    participant HW as Hardware/Broker
    participant Svc as device_service
    participant Engine as automation_engine (mash_control)
    participant Rule as AutomationRule
    participant Log as AutomationRuleLog

    HW->>Svc: update_from_mqtt(actor, valor) [Fluxo 1]
    EventBus->>Engine: device_manager.actor.value_changed(function_name, valor)
    Engine->>Rule: busca regras por sensor_function_name
    loop para cada regra ativa
        Engine->>Engine: em cooldown? avalia condition_operator/condition_value
        alt condição satisfeita e fora do cooldown
            Engine->>Svc: find_actor_external_id_by_function_name(actor_function_name)
            Engine->>Svc: set_value(actor_id, valor_resolvido) [Fluxo 2]
            Engine->>Log: grava AutomationRuleLog (sucesso/falha)
        end
    end
```

## Fluxo 5 — Reconexão manual via Monitor de Tarefas

```mermaid
sequenceDiagram
    participant Op as Operador
    participant Mon as Monitor de Tarefas (/admin/tasks)
    participant Task as TaskService
    participant MQTT as mqtt_client_service.reconnect

    Op->>Mon: clica "Executar agora" em task device_manager.mqtt_reconnect
    Mon->>Task: run_now(task_id)
    Task->>MQTT: chama função registrada via TASK_REGISTRY
    MQTT->>MQTT: stop() + start(app) — remonta o LWT do zero
    MQTT->>Task: retorna True/False
    Task->>Mon: grava TaskLog (success/failure)
```
