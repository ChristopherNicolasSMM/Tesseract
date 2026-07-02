# 01 — Visão Geral (Feature Brew Father)

## Propósito

Sincronização com a API do BrewFather. **Sem tabela de domínio
própria** — grava em `MashRecipe`/`BrewSession`
(`feature_mash_control`) com `origem_receita="BrewFather"`, via
`ingredient_resolution_service` (também de `feature_mash_control`)
pra resolver os ingredientes da receita importada contra
`addon_estoque`.

## Dependências

`feature_mash_control` (mesma Addon — chama o service de resolução
diretamente, não é uma dependência declarada em manifesto porque
Features do mesmo Addon são sempre carregadas juntas).

## Fora de escopo

Tabela própria de `BrewFatherRecipe`/`BrewFatherBatch` — **eliminada**
por decisão desta rodada (duplicava `MashRecipe`/`BrewSession`).

## Pendências

- `sync_service.py` (parse da API BrewFather, chamada ao
  `ingredient_resolution_service`) — não implementado, só desenhado
  no nível de fluxo (`features/feature_mash_control/docs/technical/03-fluxos.md`).
- Log de sincronização (`BrewFatherSync` — status, erro, raw_data) —
  desenhado, não implementado.
- `docs/manual/`, `i18n/pt_BR.json` — não escritos.
