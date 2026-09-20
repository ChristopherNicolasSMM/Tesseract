# 04 — Modelo de Dados (Addon BrewStation)

> O núcleo do Addon (`root/`) não tem tabela própria. O ER completo de
> cada Feature vive em `features/*/docs/technical/04-modelo-de-dados.md`.

Resumo de tabelas por Feature:

| Feature | Tabelas | Prefixo |
|---|---|---|
| `feature_yeast_bank` | 7 | `tesseract_brewstation_yeastbank_*` |
| `feature_mash_control` | 18 | `tesseract_brewstation_mashctrl_*` |
| `feature_brew_father` | 1 (`BrewFatherSync` — nome curto `sync`, o prefixo do CrudGen já adiciona `brewfather_`) | `tesseract_brewstation_brewfather_*` |
| `feature_ingredientes` | 4 (`Malte`/`Lupulo`/`Levedura`/`PrecoPadraoInsumo`) | `tesseract_brewstation_ingr_*` |
| `feature_envase` | 4 (`Envase`/`ItemEnvase`/`CalculoPrecificacao`/`ItemCustoIngrediente`) | `tesseract_brewstation_env_*` |

Total: 34 tabelas de domínio no Addon.

## Referências fracas cross-Addon (skill 02 — nunca FK)

| De (Feature) | Para (Addon) | Resolvido por |
|---|---|---|
| `feature_mash_control` (`AutomationRule`, `BrewPlantMapping`, `DashboardWidget`) | `addon_device_manager` | `device_function_lookup` |
| `feature_mash_control` (`RecipeIngredient`, `IngredientMapping`) | `addon_estoque` | `material_lookup` |
| `feature_ingredientes` (`Malte`/`Lupulo`/`Levedura`) | `addon_estoque` | `material_lookup` |
| `feature_envase` (`ItemEnvase`, `CalculoPrecificacao`/`ItemCustoIngrediente` via `precificacao_service`) | `addon_estoque` | `material_lookup` |

**Correção desta rodada**: as referências pra `addon_device_manager`
eram documentadas como FK cross-Feature (quando `device_manager` ainda
era Feature interna). Desde a promoção (skill 05), são referência
fraca cross-Addon — a tabela acima corrige isso.
