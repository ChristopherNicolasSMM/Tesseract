# 01 — Visão Geral (Feature Mash Control)

## Propósito

Receitas (`MashRecipe`), plantas/equipamentos (`BrewPlant`,
`BrewPlantVessel`, `BrewPlantMapping`), sessões de brassagem
(`BrewSession`, `BrewSessionStep`, `BrewSessionLog`,
`BrewSessionAlarm`), dashboards visuais (`DashboardLayout`,
`DashboardWidget`), regras de automação (`AutomationRule`,
`AutomationRuleLog`) e, a partir desta rodada, ingredientes de receita
(`RecipeIngredient`), cache de resolução de ingrediente
(`IngredientMapping`) e histórico de versão de receita
(`RecipeHistory`).

Portado de `plugin_mash_control` (BrewStation original) — **escopo
deliberadamente CRUD nesta fase** (decisão registrada no BACKLOG.md).

## Fora do escopo desta fase (decisão registrada)

A lógica de controle em tempo real do BrewStation original —
controlador PID, motor de automação que avalia sensores continuamente,
scheduler de processo — **não foi portada**. Ver BACKLOG.md.

## Dependências

- **`addon_device_manager`** (Addon independente, promovido — skill
  05): `BrewPlantMapping`, `DashboardWidget` e `AutomationRule`
  referenciam `DeviceFunction` via **referência fraca**
  (`device_function_lookup.py`, service público), **não mais FK
  cross-Feature** — correção de documentação desta rodada; o código
  já estava certo, só o doc não tinha acompanhado.
- **`addon_estoque`** (Addon independente, novo nesta rodada):
  `RecipeIngredient`/`IngredientMapping` referenciam `Material` via
  referência fraca (`material_lookup.buscar_material_por_termo()`),
  usada no fluxo de resolução de ingrediente na importação de receita.

## Receita — papel ampliado nesta rodada

`MashRecipe`/`BrewSession` **não são promovidos** para o root de
`addon_brewstation` — continuam aqui, mas passam a ser referenciados
por outras Features do mesmo Addon (`feature_ingredientes`,
`feature_brew_father`, `feature_envase`) via **FK real** (cross-Feature,
mesmo Addon, skill 02 permite). `Receita` agora serve de base para:
controle de brassagem (já existia), controle de lote (já existia,
`BrewSession`), cálculo de preço (parked) e envase (`feature_envase`,
nesta rodada) — os dois últimos consomem `addon_estoque`.

## Origem multi-fonte e versionamento (novo)

`MashRecipe` ganha `origem_receita` (`BrewFather` | `BeerSmith` |
`BeerXML` | `Manual`), `origem_receita_id` e `versao`, com
`unique(name, versao)`. **Toda modificação salva cria uma nova
versão** (nova linha em `MashRecipe`, nunca update in-place de uma
versão já salva) — cada versão é imutável depois de criada.
`RecipeHistory` guarda snapshot completo (JSON) de cada transição,
pra comparação/consulta, complementar às linhas versionadas.

## `recipe_data` (JSON) — substituído

`MashRecipe.recipe_data` é removido. Ingredientes passam a ser linhas
normalizadas em `RecipeIngredient`, cada uma resolvida (ou pendente de
resolução) contra `addon_estoque.Material` — ver `03-fluxos.md` pro
fluxo de resolução/de-para.

## Tabelas

15 tabelas nesta rodada (12 existentes + `RecipeIngredient` +
`IngredientMapping` + `RecipeHistory`), prefixo
`tesseract_brewstation_mashctrl_*`. Ver `04-modelo-de-dados.md`.

## Pendências

- Telas de de-para/resolução de ingrediente — não mapeadas.
- `ingredient_resolution_service` reaproveitável por futuras
  integrações (`feature_beersmith`, import de BeerXML) — desenhado no
  nível de fluxo, não implementado.
