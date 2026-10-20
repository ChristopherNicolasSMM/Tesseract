# 06 — Manutenção e Expansão (`addon_device_manager`)

## Adicionar um novo tipo de função

Não precisa de migration — `DeviceFunction` é uma tabela normal,
basta cadastrar pela tela ou API. Se a função tiver faixa
(`min_value`/`max_value`), a validação em `device_service._validate_range()`
passa a valer automaticamente para qualquer `DeviceActor` que a use —
nenhum código novo necessário.

## Integração MQTT real — status

**Implementada** (Fase D, 2026-06-29) — `mqtt_client_service.py`
conecta de fato a um broker real. Para habilitar:

```bash
MQTT_ENABLED=true
MQTT_BROKER_HOST=...
MQTT_BROKER_PORT=1883
MQTT_TOPIC_PREFIX=brewery   # ou outro, livre
```

Nunca liga em ambiente de teste (`TESTING=True`, guard explícito em
`core/app_factory.py`). Cada `DeviceActor` precisa de `mqtt_config`
(em `config_json`) com `state_topic` e/ou `command_topic` para
participar de fato da comunicação — sem isso, fica só com cache local
(`get_value`/`set_value` continuam funcionando, só não há hardware
real do outro lado).

## Adicionar um novo protocolo (além de MQTT)

Decisão registrada (`docs/skills/05-*.md`, §2.5): MQTT é o único
protocolo da v1, deliberadamente. Se/quando precisar de outro
(Modbus, Serial), a recomendação é uma **nova Feature** dentro deste
mesmo Addon (ex.: `feature_modbus_bridge`), não um redesenho do core.

## Adicionar uma nova ação para o motor de automação

`AutomationRule.actor_action` hoje suporta `ON`/`OFF`/`SET_VALUE`/
`TOGGLE` (implementado em `feature_mash_control/services/automation_engine.py`,
não neste Addon). Para adicionar uma ação nova, editar
`_resolve_target_value()` lá — este Addon não precisa saber dos
detalhes, só recebe o valor final via `set_value()`.

## Registrar uma nova função agendável no Monitor de Tarefas

```python
from core.task_registry import register_task

register_task("device_manager.minha_funcao", lambda: minha_logica())
```

Chamar dentro de `AddonDeviceManager.register_routes()` (roda antes
de `create_all_pending_tables()` — só registro em memória, nunca
grava no banco ali). A `ScheduledTask` real (com agendamento) é
criada pelo operador via UI (`/admin/tasks`), nunca seedada
automaticamente por código (decisão registrada no `BACKLOG.md`, Fase
9 — evita decidir agendamento/aprovação sem o operador pedir).

## Onde fica o log de rotina

`addons/addon_device_manager/logs/integration.log` (rotativo, 5
arquivos de 5 MB) — configurável via `addon.json: logging.*`. Erro
que importa para operação (valor fora de faixa, falha de
fail-safe) sempre sobe **também** para o log global do Core — nunca
fica só ali.

## Observações recebidas — aquecimento Mash Control (20/10/2026)

`device_service.get_observation(identifier)` retorna DTO com valor, `observed_at`,
`source=mqtt_state` e identificação externa. Apenas recepção por `update_from_mqtt`
atualiza esses campos; comandos `set_value` não são observações. Após persistir o
estado recebido, publica-se `device_manager.actor.observation_received` com
`function_name`. Cache/evento anteriores permanecem compatíveis. Dados antigos
sem observação explícita retornam `None` até nova recepção; nunca usar
`last_seen_at` de um comando para comprovar frescor de telemetria.

## Telemetria Bridge v1 — entrega 3

O ingresso MQTT decodifica envelopes JSON antes de chamar `update_from_mqtt`. Este
aceita `heating_telemetry`/`retained` opcionais e valida versão, sequência/boot, data
e identidade. `get_heating_telemetry` retorna cópia de `runtime.bridge_heating`; não
há novas colunas. Comandos não atualizam esse estado e respeitam `local_only`
recebido (OFF permitido). Retenção não renova observações de controle. O importador
Bridge preenche tópicos MQTT ausentes sem substituir os personalizados. O contrato
completo está em `docs/technical/08-aquecimento-hlt-sparge.md` na raiz do projeto.
