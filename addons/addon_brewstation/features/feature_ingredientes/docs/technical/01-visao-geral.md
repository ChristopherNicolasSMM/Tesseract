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

3 tabelas: `Malte`, `Lupulo`, `Levedura`. `IngredienteReceita` (linha
de ingrediente de uma receita) **não mora aqui** — mora em
`feature_mash_control`, junto de `MashRecipe` (decisão desta rodada).

## Pendências

- Telas de cadastro/edição — não mapeadas ainda.
- `docs/manual/` — não escrito.
- `i18n/pt_BR.json` — não escrito.
