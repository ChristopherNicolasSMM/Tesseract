# 01 — Visão Geral (`addon_device_manager`)

## Propósito

Gestão de dispositivos IoT (sensores/atuadores) e comunicação MQTT
real com hardware físico ou emulado: catálogo de funções
(`DeviceFunction`), metadados de dispositivo (`DeviceMetadata`),
atores que associam porta de device a função (`DeviceActor`), e
dispositivos emulados para testar sem hardware real
(`EmulatedDevice`).

Histórico: nasceu como `feature_device_manager`, Feature de
`addon_brewstation` (portada de `plugin_device_manager`, BrewStation
original). Promovido a Addon independente na **Fase 9** (ver
`docs/skills/05-proposta-addon-device-manager-e-mqtt.md` para o
histórico completo da decisão, incluindo as 4 FKs cross-Addon
removidas na promoção).

## O que este Addon expõe (`provides`)

| Capacidade | Quem consome hoje |
|---|---|
| `device_data` | — |
| `device_actor_data` | `feature_mash_control` (referência fraca por nome, nunca FK) |
| `device_function_data` | `feature_mash_control` |

## Dependências (`requires`)

Nenhuma — é o Addon mais "de base" do ecossistema de automação,
referenciado por `feature_mash_control` via serviço público, nunca
FK direta (skill 02).

## Camadas internas

| Camada | Arquivo | Responsabilidade |
|---|---|---|
| Modelo | `root/model/device_function.py`, `device_metadata.py`, `device_actor.py`, `emulated_device.py` | Cadastro (CrudGen) |
| Serviço público | `root/services/device_service.py` | API mínima `get_value`/`set_value`/`on_change` (por actor) + EventBus do Core (`device_manager.actor.value_changed`, cross-Addon) — ponto de entrada para qualquer outro módulo |
| Serviço público | `root/services/device_function_lookup.py` | Resolução de `DeviceFunction` por nome (referência fraca cross-Addon) |
| Integração externa | `root/services/mqtt_client_service.py` | Cliente MQTT real — conecta, publica, assina, registra o LWT agregado |
| Logging | `root/services/integration_logger.py` | Log de rotina local (`logs/integration.log`), separado do log global do Core |

`device_service.py` e `device_function_lookup.py` **não são gerados
pelo CrudGen** — são os pontos de extensão manuais e estáveis deste
Addon (mesmo papel que um arquivo `_hooks.py` desempenha para
customização, mas para lógica de runtime/cross-módulo).

## Melhorias sobre o original (BrewStation)

- **`relationship()` ORM habilitado** — o BrewStation original
  desabilitava de propósito porque o mecanismo de prefixo dele
  quebrava a configuração do mapper. No Tesseract isso foi testado e
  funciona.
- **PK Integer + `external_id` UUID** — skill 02, "Regra de PK
  externa". O original usava UUID como PK; aqui o `id` interno é
  Integer (consistente com toda outra tabela), e o UUID vira
  `external_id`, exposto a integrações externas (ex.: usado como
  fallback de identificador em tópico MQTT quando `config_json` não
  define um explicitamente).
- **Bug corrigido**: `EmulatedDevice.functions_config` usava
  `default={}` (dict mutável compartilhado entre instâncias) —
  trocado por `default=lambda: {}`.

## Tabelas

`tesseract_dvm_function`, `tesseract_dvm_device`, `tesseract_dvm_actor`,
`tesseract_dvm_emulated_device` (prefixo de Addon, dois níveis — skill
02; renomeadas de `tesseract_brewstation_dvm_*` na promoção, migration
`4a8524f00549`).
