# 05 — Casos de Uso (`addon_device_manager`)

## UC01 — Cadastrar função de dispositivo
- **Ator**: usuário com `device_functions.create`
- **Fluxo**: define nome interno (único, vira referência fraca para
  outros módulos), categoria (sensor/atuador/híbrido), tipo de dado,
  faixa (`min_value`/`max_value`, opcional).
- **Fluxo alternativo**: faixa omitida — qualquer valor é aceito sem
  validação (ver `device_service._validate_range()`).

## UC02 — Cadastrar dispositivo IoT
- **Ator**: usuário com `device_metadatas.create`
- **Fluxo**: nome, tipo, protocolo — `external_id` gerado
  automaticamente.

## UC03 — Associar porta de um dispositivo a uma função (Ator)
- **Ator**: usuário com `device_actors.create`
- **Pré-condição**: dispositivo e função já existem
- **Permissão**: `device_actors.create`
- **Fluxo alternativo (atuador de risco)**: se marcar `is_risk`,
  define também `failsafe_value` — esse ator passa a entrar no LWT
  agregado na próxima conexão MQTT (`mqtt_client_service.start()`).

## UC04 — Emular um dispositivo sem hardware real
- **Ator**: usuário com `emulated_devices.create`
- **Fluxo**: escolhe modo de emulação (sine_wave/random_walk/manual)

## UC05 — Atuador recebe comando de outro módulo
- **Ator**: outro Addon (ex.: `feature_mash_control`, via
  `automation_engine.py`)
- **Pré-condição**: ator existe, `config_json` tem `mqtt_config.command_topic`
  se o comando deve chegar ao hardware de fato
- **Fluxo**: chama `device_service.set_value(identificador, valor)` —
  nunca FK/ORM direto (skill 02)
- **Fluxo alternativo (falha)**: valor fora da faixa de
  `DeviceFunction` → comando **rejeitado**, `set_value` retorna
  `False`, nada é publicado no broker.

## UC06 — Sensor publica leitura via MQTT
- **Ator**: hardware (real, via `tesseract-device-bridge`, ou
  emulado)
- **Fluxo**: publica no `state_topic`; `mqtt_client_service` resolve o
  `DeviceActor` correspondente e chama
  `device_service.update_from_mqtt()`.
- **Fluxo alternativo (fora de faixa)**: valor é registrado mesmo
  assim (é dado observado, não comando) — mas gera log de erro
  global, nunca só local.

## UC07 — Operador força reconexão MQTT
- **Ator**: usuário com permissão `admin`
- **Pré-condição**: task `device_manager.mqtt_reconnect` criada no
  Monitor de Tarefas (`/admin/tasks`)
- **Fluxo**: clica "Executar agora" → `mqtt_client_service.reconnect()`
  → `stop()` + `start()` → LWT remontado do zero (inclui qualquer
  ator marcado `is_risk` depois da última conexão).

## UC08 — Regra de automação dispara ação a partir de leitura de sensor
- **Ator**: sistema (event-driven, sem ator humano direto)
- **Pré-condição**: `AutomationRule` ativa em `feature_mash_control`
  referenciando este Addon por `sensor_function_name`/
  `actor_function_name` (referência fraca)
- **Fluxo**: UC06 publica `device_manager.actor.value_changed` no EventBus → `automation_engine`
  avalia a condição → se verdadeira e fora do cooldown, executa UC05
  → grava log no Addon dependente (`AutomationRuleLog`), não aqui.
- Ver `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`, seção
  5 (Fluxo 4), para o diagrama completo.
