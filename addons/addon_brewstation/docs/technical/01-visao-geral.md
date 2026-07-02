# 01 — Visão Geral (Addon BrewStation)

## Propósito

Addon de domínio para gestão de cervejaria caseira. Núcleo do Addon
(`root/`) continua sem model próprio — `MashRecipe`/`BrewSession`
(Receita/Lote canônicos) permanecem dentro de `feature_mash_control`,
não foram promovidos para o root nesta rodada (decisão explícita:
fazem sentido só dentro deste Addon, diferente do caso `device_manager`,
que era genérico o bastante pra virar Addon próprio).

## Dependências

`requires: ["device_manager", "estoque"]` — **corrigido nesta rodada**.
O manifesto real estava desatualizado: ainda listava `feature_device_manager`
como Feature interna (a pasta não existe mais desde a promoção, skill
05) e não declarava a dependência de `addon_device_manager` no nível
do Addon. Também ganha `estoque` (Addon novo, gestão genérica de
materiais).

## O que expõe (`provides`)

`recipe_data`, `inventory_data` (mantido do manifesto original).

## Features

| Feature | Entidades | Docs |
|---|---|---|
| `feature_yeast_bank` | 8 | `features/feature_yeast_bank/docs/technical/01-visao-geral.md` |
| `feature_mash_control` | 15 (12 + 3 novas nesta rodada) | `features/feature_mash_control/docs/technical/01-visao-geral.md` |
| `feature_brew_father` | 0 tabela própria (sync service + log) | `features/feature_brew_father/docs/technical/01-visao-geral.md` (a criar) |
| `feature_ingredientes` | 3 (Malte/Lúpulo/Levedura) | `features/feature_ingredientes/docs/technical/01-visao-geral.md` |
| `feature_envase` | 2 (Envase/ItemEnvase) | `features/feature_envase/docs/technical/01-visao-geral.md` |

**Correção desta rodada**: `feature_device_manager` **não existe mais**
como Feature deste Addon — foi promovida a `addon_device_manager`
(Addon independente, skill 05). `feature_mash_control` referencia
`DeviceFunction` por referência fraca (service público
`device_function_lookup`), não mais FK cross-Feature.

FK cross-Feature existente hoje (mesmo Addon, permitida pela skill 02):
`feature_envase.Envase.lote_id` → `feature_mash_control.BrewSession.id`;
`feature_mash_control.RecipeIngredient.recipe_id` →
`feature_mash_control.MashRecipe.id` (interna à própria Feature).

## Referências fracas cross-Addon (skill 02 — nunca FK)

- `feature_mash_control` → `addon_device_manager` (sensor/atuador de
  regra de automação, mapeamento de vasilhame, widget de dashboard)
- `feature_mash_control` → `addon_estoque` (resolução de ingrediente
  de receita, `RecipeIngredient.material_id`)
- `feature_ingredientes` → `addon_estoque` (`material_id` de
  Malte/Lúpulo/Levedura)
- `feature_envase` → `addon_estoque` (`material_id` de `ItemEnvase`,
  baixa síncrona de estoque)

## Fora de escopo

Domínio de Dispositivos do legado `plugin_integ_bFather`
(BrewStation original, pré-Tesseract) — eliminado, coberto por
`addon_device_manager`. Domínio de Cálculo/precificação
(base de custo, base dedutiva, impostos cadastrados) — parked, sessão
dedicada futura.
