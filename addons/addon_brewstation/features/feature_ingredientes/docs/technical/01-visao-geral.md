# 01 — Visão Geral (Feature Ingredientes)

## Propósito

Especificações de cervejaria de Malte, Lúpulo e Levedura —
complementares ao `Material` genérico de `addon_estoque` (nome,
unidade, peso, volume...). Cada tabela aqui carrega só o que é
específico do tipo (ex.: `cor_ebc` de malte), referenciando o
`Material` correspondente fracamente (`material_id`, sem FK — skill
02, cross-Addon).

## Dependências

`addon_estoque` (via referência fraca, `requires: []` no manifesto
desta Feature porque a dependência real está declarada no nível do
Addon `addon_brewstation`, não repetida aqui — ver `addon.json`).

## Nota de relação com `feature_yeast_bank`

`Levedura` (aqui) e `YeastStrain` (`feature_yeast_bank`) são conceitos
relacionados, mas **não são a mesma coisa**: `YeastStrain` é gestão de
banco de cepas físicas (viabilidade, congelamento, starters);
`Levedura` aqui é a especificação de ingrediente pra cálculo de
receita (atenuação, temperatura de fermentação, floculação). Não há FK
entre elas nesta rodada — é uma pendência observada, não resolvida.

## Tabelas

4 tabelas: `Malte`, `Lupulo`, `Levedura`, `PrecoPadraoInsumo`.
`IngredienteReceita` (linha de ingrediente de uma receita) **não mora
aqui** — mora em `feature_mash_control`, junto de `MashRecipe`
(decisão desta rodada).

## `PrecoPadraoInsumo` — preço de referência quando não há compra real

Uma linha por tipo de insumo (`malte`/`lupulo`/`levedura` — não por
`Material` individual, nem genérico o bastante para cobrir qualquer
`Categoria`/`TipoProduto` de `addon_estoque`; decisão de escopo
propositalmente estreita). Consumido por
`feature_envase/services/precificacao_service.py` quando um Material
usado numa receita nunca teve entrada real registrada (`Saldo` vazio)
— cai nesse valor padrão em vez de custar `0.0` silenciosamente. Ver
`feature_envase/docs/technical/03-fluxos.md` para o fluxo completo de
resolução de preço.

## Pendências

- Telas de cadastro/edição específicas (além do CRUD padrão gerado) —
  não mapeadas ainda.
- `i18n/pt_BR.json` — não escrito (gap conhecido em quase todo o
  Addon, registrado em `BACKLOG.md`).
