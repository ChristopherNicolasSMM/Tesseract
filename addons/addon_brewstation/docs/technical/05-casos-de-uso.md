# 05 — Casos de Uso (Addon BrewStation)

Casos de uso detalhados vivem em cada Feature
(`features/*/docs/technical/05-casos-de-uso.md`). Em nível de Addon,
os casos de uso transversais (cruzam mais de uma Feature ou Addon)
são:

## UC01 — Regra de automação cruza Feature e Addon

- **Ator**: usuário com `automation_rules.create`
- **Fluxo**: cadastra uma `AutomationRule` (`feature_mash_control`)
  apontando para um sensor e um atuador, ambos `DeviceFunction`
  (`addon_device_manager`, referência fraca cross-Addon)
- **Limitação atual**: a regra fica registrada, mas nenhum motor a
  executa de fato (sem job runner/scheduler ainda)

## UC02 — Envase consome Receita/Lote e dá baixa em Estoque — novo

- **Ator**: usuário com `envase.create`
- **Fluxo**: `feature_envase` referencia `BrewSession`
  (`feature_mash_control`, FK real mesmo Addon) e, ao registrar,
  chama `addon_estoque` (referência fraca cross-Addon) pra dar baixa
  nos Materiais de embalagem usados
- Ver detalhe em `features/feature_envase/docs/technical/05-casos-de-uso.md`

## UC03 — Importação de receita resolve ingrediente contra Estoque — novo

- **Ator**: usuário com `mash_recipes.import`
- **Fluxo**: `feature_brew_father` (ou futura `feature_beersmith`)
  importa receita, `feature_mash_control` resolve cada ingrediente
  contra `addon_estoque` via referência fraca — ver detalhe em
  `features/feature_mash_control/docs/technical/05-casos-de-uso.md`
  (UC05)
