# 03 — Fluxos (Addon BrewStation)

## Sequência: dependência entre Features no boot

```mermaid
sequenceDiagram
    participant MM as ModuleManager
    participant MC as feature_mash_control
    participant BF as feature_brew_father
    participant ING as feature_ingredientes
    participant ENV as feature_envase

    MM->>MC: importa models (MashRecipe, RecipeIngredient, ...)
    MM->>BF: importa (sem model proprio)
    MM->>ING: importa models (Malte/Lupulo/Levedura)
    MM->>ENV: importa models (Envase/ItemEnvase, FK real -> mashctrl.session)
    Note over MM: só DEPOIS de importar TUDO, aplica prefixo de tabela
    MM->>MM: apply_table_prefix() em lote
```

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema) para o
porquê dessa ordem.

## Fluxos cross-Addon desta rodada

`feature_mash_control` e `feature_envase` chamam services públicos de
`addon_device_manager`/`addon_estoque` — ver
`features/feature_mash_control/docs/technical/03-fluxos.md` e
`features/feature_envase/docs/technical/03-fluxos.md` para o detalhe
sequencial completo.

Fluxos específicos de cada Feature (caminho feliz da operação
principal) estão em `features/*/docs/technical/03-fluxos.md`.
