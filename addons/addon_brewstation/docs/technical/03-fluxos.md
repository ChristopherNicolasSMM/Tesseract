# 03 — Fluxos (Addon BrewStation)

## Sequência: dependência entre Features no boot

```mermaid
sequenceDiagram
    participant MM as ModuleManager
    participant DM as feature_device_manager
    participant MC as feature_mash_control

    MM->>DM: importa models (DeviceFunction, etc.)
    MM->>MC: importa models (referencia DeviceFunction via FK)
    Note over MM: só DEPOIS de importar TUDO, aplica prefixo de tabela
    MM->>MM: apply_table_prefix() em lote
```

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema) para o
porquê dessa ordem — FK cross-Feature quebrava se o prefixo fosse
aplicado Feature por Feature.

Fluxos específicos de cada Feature (caminho feliz da operação
principal) estão em `features/*/docs/technical/03-fluxos.md`.
