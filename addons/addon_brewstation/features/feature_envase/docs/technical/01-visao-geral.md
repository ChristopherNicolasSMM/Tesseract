# 01 — Visão Geral (Feature Envase)

## Propósito

Evento de empacotamento de um Lote (`BrewSession`, de
`feature_mash_control`) num produto acabado. Desde a skill 26
(2026-09-01), `Envase` aponta pro **Material resultante** — o produto
acabado já cadastrado em `addon_estoque` (ex.: "Growler 1L Valirian
Pilsen") — e os componentes de embalagem usados são resolvidos
automaticamente pela **Composição** (BOM) desse Material, não mais
digitados um a um. A baixa de estoque dos componentes é síncrona, via
service público de `addon_estoque`.

Além disso, esta Feature também dispara (ou confirma que já foi feita)
a baixa de estoque dos **insumos da receita** (malte/lúpulo/levedura)
usados no lote — função que hoje mora em `feature_mash_control`
(`ingredient_consumption_service.py`), chamada daqui como fallback se
o operador ainda não tiver confirmado isso na tela do lote (ver
`03-fluxos.md`).

## Dependências

`feature_mash_control` (FK real, cross-Feature, mesmo Addon —
`lote_id` aponta pra `session.id`; e chamada de função, não FK, pra
`ingredient_consumption_service.confirmar_consumo_ingredientes()`).
`addon_estoque` (referência fraca + chamada síncrona de service
público, cross-Addon — `material_lookup.get_material()`,
`material_lookup.get_composicao()`, `estoque_service.registrar_movimentacao()`).

## Origem

Absorve o domínio `Envase`/`TipoEmbalagem`/`Embalagem` do legado
`plugin_integ_bFather` — a parte de catálogo/estoque de embalagem foi
completamente absorvida por `addon_estoque` (`Material`, com
Composição pra descrever "do que é feito" um produto acabado); só o
**evento** de envasar ficou aqui.

## Tabelas

2 tabelas: `Envase`, `ItemEnvase`. **`ItemEnvase` é histórico desde a
skill 26** — continua existindo com dado antigo, mas não recebe mais
INSERT (ver `04-modelo-de-dados.md`).

## Pendências

- Telas de cadastro do Envase em si — não mapeadas.
- Regra de bloqueio (ou não) de envase/consumo de insumo sem saldo
  suficiente — mesma pendência de `addon_estoque`, agora relevante nos
  dois pontos de baixa desta Feature (componentes de embalagem E
  insumo de receita), não só um.
- `i18n/pt_BR.json` — não escrito (gap conhecido em quase todo o
  Addon, registrado em `BACKLOG.md`).
