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
por decisão de sessão anterior (duplicava `MashRecipe`/`BrewSession`).

## Status real (corrigido nesta rodada — doc estava desatualizado)

`sync_service.py`, `brewfather_client.py`, `ingredient_autocreate_service.py`
e o model `BrewFatherSync` (log de sincronização) **já estão
implementados** — a versão anterior deste documento dizia o oposto
("não implementado, só desenhado"), o que não reflete mais o código
real. Ver `docs/technical/06-manutencao-e-expansao.md` (nova) para o
funcionamento prático completo.

## Pendências reais

- Item (c) do `BACKLOG.md` — adjuntos (`miscs[]`) e água (`water`) da
  API BrewFather, decidido mas não implementado.
- `docs/manual/`, `i18n/pt_BR.json` — não escritos.
