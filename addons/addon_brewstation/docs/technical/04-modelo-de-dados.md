# 04 — Modelo de Dados (Addon BrewStation)

> O núcleo do Addon (`root/`) não tem tabela própria. O ER completo de
> cada Feature vive em `features/*/docs/technical/04-modelo-de-dados.md`.

Resumo de tabelas por Feature:

| Feature | Tabelas | Prefixo |
|---|---|---|
| `feature_yeast_bank` | 8 | `tesseract_brewstation_yeastbank_*` |
| `feature_mash_control` | 15 (12 + `recipe_ingredient` + `ingredient_mapping` + `recipe_history`, nesta rodada) | `tesseract_brewstation_mashctrl_*` |
| `feature_brew_father` | 0 (sync service + log, sem tabela de domínio) | `tesseract_brewstation_brewfather_*` (log de sync, quando implementado) |
| `feature_ingredientes` | 3 (`Malte`/`Lupulo`/`Levedura`, nova) | `tesseract_brewstation_ingr_*` |
| `feature_envase` | 2 (`Envase`/`ItemEnvase`, nova) | `tesseract_brewstation_env_*` |

Total: 28 tabelas de domínio no Addon (24 anteriores + 4 novas —
`recipe_ingredient`, `ingredient_mapping`, `recipe_history` em
`feature_mash_control`, mais as 5 de `feature_ingredientes`/
`feature_envase` menos a remoção de `recipe_data`, que não era
tabela própria).

## Referências fracas cross-Addon (skill 02 — nunca FK)

| De (Feature) | Para (Addon) | Resolvido por |
|---|---|---|
| `feature_mash_control` (`AutomationRule`, `BrewPlantMapping`, `DashboardWidget`) | `addon_device_manager` | `device_function_lookup` |
| `feature_mash_control` (`RecipeIngredient`, `IngredientMapping`) | `addon_estoque` | `material_lookup` |
| `feature_ingredientes` (`Malte`/`Lupulo`/`Levedura`) | `addon_estoque` | `material_lookup` |
| `feature_envase` (`ItemEnvase`) | `addon_estoque` | `material_lookup` |

**Correção desta rodada**: as referências pra `addon_device_manager`
eram documentadas como FK cross-Feature (quando `device_manager` ainda
era Feature interna). Desde a promoção (skill 05), são referência
fraca cross-Addon — a tabela acima corrige isso.
