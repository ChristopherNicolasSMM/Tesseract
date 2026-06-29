# 02 — Diagrama C4 (`addon_device_manager`)

No nível Addon, gera-se só **Componente** (skill 04) — Contexto e
Container já estão cobertos em `docs/technical/02-diagrama-c4.md` da
raiz do projeto.

## Componente

```mermaid
C4Component
    title addon_device_manager — Componentes internos

    Container_Boundary(dm, "addon_device_manager") {
        Component(model, "Models", "SQLAlchemy", "DeviceFunction, DeviceMetadata, DeviceActor, EmulatedDevice")
        Component(svc, "device_service", "Python", "API pública: get_value/set_value/on_change + publica EventBus")
        Component(lookup, "device_function_lookup", "Python", "Resolução por nome (cross-Addon, sem FK)")
        Component(mqtt, "mqtt_client_service", "paho-mqtt", "Conecta, publica, assina, LWT agregado")
        Component(log, "integration_logger", "Python logging", "Log de rotina local (RotatingFileHandler)")
        Component(ctrl, "Controllers/API", "Flask Blueprints", "CRUD de Function/Device/Actor/EmulatedDevice")
    }

    System_Ext(broker, "Broker MQTT", "Mosquitto ou similar")
    System_Ext(bridge, "tesseract-device-bridge", "Repositório separado — GPIO físico")
    Container(mash, "feature_mash_control", "Addon dependente", "automation_engine.py")
    Container(taskmon, "Monitor de Tarefas (Core)", "/admin/tasks", "TaskService + task_registry")

    Rel(ctrl, model, "CRUD via CrudGen")
    Rel(svc, model, "lê/escreve config_json[\"runtime\"]")
    Rel(svc, mqtt, "publish() quando aplicável")
    Rel(svc, log, "eventos de rotina")
    Rel(mqtt, broker, "MQTT (pub/sub + LWT)")
    Rel(broker, bridge, "MQTT (pub/sub + LWT)")
    Rel(mash, svc, "get_value/set_value (chamada direta) + EventBus (cross-Addon, nunca FK/ORM direto)")
    Rel(mash, lookup, "resolve DeviceFunction por nome")
    Rel(taskmon, mqtt, "executa device_manager.mqtt_reconnect sob demanda")
```

## Observações de fronteira (skill 02)

- `feature_mash_control` (Addon `brewstation`) nunca importa
  `root/model/*` deste Addon — só `device_service`/
  `device_function_lookup`, e sempre recebendo `string`/valor
  primitivo, nunca o objeto ORM (`DeviceActor`) em si. Essa regra foi
  corrigida durante a implementação da Fase E (o callback de
  o mecanismo original (substituído pelo EventBus do Core na Fase G) vazava o objeto `DeviceActor` —
  corrigido para entregar só `function_name: str`).
- `addon_device_manager` nunca importa nada de `feature_mash_control`
  — a dependência só existe na direção `mash_control → device_manager`
  (declarada em `feature_mash_control/feature.json: requires`).
- O sistema de Tasks (Core) chama este Addon só através de uma função
  registrada (`core.task_registry.register_task`), nunca o contrário.
