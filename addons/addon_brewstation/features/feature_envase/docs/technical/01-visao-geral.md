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

4 tabelas: `Envase`, `ItemEnvase`, `CalculoPrecificacao`,
`ItemCustoIngrediente`. **`ItemEnvase` é histórico desde a skill 26**
— continua existindo com dado antigo, mas não recebe mais INSERT (ver
`04-modelo-de-dados.md`).

## Dois mecanismos de custo — não confundir

Esta Feature tem **dois** cálculos de custo separados, com propósito
diferente e sem um chamar o outro:

| | `calcular_custo_industrializacao_envase()` | `precificacao_service.py` (`simular`/`calcular_e_salvar`) |
|---|---|---|
| Desde | Skill 26 | Sessão de precificação (proposta-precificacao-envase.md) |
| Persiste algo? | Não — só calcula, sob demanda | Sim — `CalculoPrecificacao`/`ItemCustoIngrediente`, se `calcular_e_salvar` |
| Custo de insumo (cerveja) | Rateia `BrewSession.custo_total_insumos` pelos litros do Envase | Recalcula do zero, item a item, direto de `RecipeIngredient` |
| Custo de embalagem | Via `Composicao` do Material resultante × `Saldo.custo_medio` | Via `ItemEnvase` do `envase_id` informado × `Saldo.custo_medio` |
| Margem/impostos (lucro, IPI, ICMS) | Não calcula | Sim — é o propósito principal |
| Tela | Nenhuma ainda (só service) | `controller/precificacao.py` |

**Achado real, registrado como pendência (`06-manutencao-e-expansao.md`)**:
o cálculo de embalagem do `precificacao_service` lê `ItemEnvase` — a
mesma tabela que `envase_estoque_service.registrar_envase()` **parou
de popular** desde a skill 26 (ver seção "Dois mecanismos" acima e
`04-modelo-de-dados.md`). Para qualquer Envase criado depois da skill
26, `custo_embalagem_total` calculado por `precificacao_service` vem
`0.0` — não por falta de preço, mas porque não há linha de
`ItemEnvase` para ler. Isso não foi corrigido nesta auditoria de
documentação (é achado de código, não de doc) — só está registrado
para não ser confundido com bug de preço.

## Pendências

- Telas de cadastro do Envase em si — não mapeadas.
- Regra de bloqueio (ou não) de envase/consumo de insumo sem saldo
  suficiente — mesma pendência de `addon_estoque`, agora relevante nos
  dois pontos de baixa desta Feature (componentes de embalagem E
  insumo de receita), não só um.
- `i18n/pt_BR.json` — não escrito (gap conhecido em quase todo o
  Addon, registrado em `BACKLOG.md`).
