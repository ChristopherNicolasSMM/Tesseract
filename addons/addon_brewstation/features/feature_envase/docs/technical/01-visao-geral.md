# 01 — Visão Geral (Feature Envase)

## Propósito

Evento de empacotamento de um Lote (`BrewSession`, de
`feature_mash_control`). Quando um envase é registrado, dá baixa
síncrona no estoque dos Materiais de embalagem usados, via service
público de `addon_estoque`.

## Dependências

`feature_mash_control` (FK real, cross-Feature, mesmo Addon — `lote_id`
aponta pra `session.id`). `addon_estoque` (referência fraca +
chamada síncrona de service público, cross-Addon).

## Origem

Absorve o domínio `Envase`/`TipoEmbalagem`/`Embalagem` do legado
`plugin_integ_bFather` — a parte de catálogo/estoque de embalagem foi
completamente absorvida por `addon_estoque` (`Material` categoria
`"embalagem"`); só o **evento** de envasar ficou aqui.

## Tabelas

2 tabelas: `Envase`, `ItemEnvase`.

## Pendências

- Telas de cadastro do Envase em si — não mapeadas.
- Regra de bloqueio (ou não) de envase sem saldo suficiente de
  embalagem — mesma pendência de `addon_estoque`.
- `docs/manual/`, `i18n/pt_BR.json` — não escritos.
