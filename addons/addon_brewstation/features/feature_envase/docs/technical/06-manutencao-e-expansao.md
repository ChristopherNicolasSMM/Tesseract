# 06 — Manutenção e Expansão (Feature Envase)

## Adicionar um campo a `Envase`

1. Editar `model/envase.py`.
2. `python run.py generate --model addons/addon_brewstation/features/feature_envase/model/envase.py --addon brewstation --feature envase --overwrite`
3. Hooks (`*_hooks.py`, `_acoes_em_massa_extra.html`,
   `_detail_extra.html`) preservados automaticamente (skill 25).

`ItemEnvase` não deveria mais ganhar campos novos — é tabela histórica
(ver `04-modelo-de-dados.md`); qualquer necessidade nova de "o que
compõe um produto acabado" é modelada em `Composicao`
(`addon_estoque`), não aqui.

## Resolver a pendência de bloqueio por saldo insuficiente

Mesma pendência em aberto do `addon_estoque` (ver
`addons/addon_estoque/docs/technical/05-casos-de-uso.md`, UC-02) —
hoje se aplica em **dois** pontos desta Feature: a baixa de
componentes de embalagem (`registrar_envase`) e a baixa de insumo de
receita (`ingredient_consumption_service.confirmar_consumo_ingredientes`,
em `feature_mash_control`). Nenhum dos dois bloqueia hoje, só deixa o
saldo negativo — coerente decidir os três casos juntos (o terceiro
sendo `Movimentação` de saída manual em `addon_estoque`), já que os
três chamam o mesmo `estoque_service.registrar_movimentacao()`.

## Como o Envase resolve os componentes (skill 26 — sem tabela própria)

`Envase` não guarda mais nenhuma lista de componentes própria — isso é
resolvido em runtime via `material_lookup.get_composicao(material_resultante_id)`
(`addon_estoque`, referência fraca + chamada síncrona, nunca FK/ORM
direto). Se um dia a Composição de um Material resultante mudar
**depois** de um Envase já ter sido registrado, isso não afeta o
Envase antigo (a baixa já aconteceu, é histórico) — só afeta o
próximo Envase feito com esse mesmo Material.

## `ItemEnvase` — decisão de remoção física, em aberto

A tabela ficou como histórico (skill 26 não removeu nada, só parou de
inserir) — decisão de dropar a tabela/FK de vez, quando o novo fluxo
estiver validado em produção por tempo suficiente, ainda não foi
tomada. Ver `docs/skills/26-proposta-envase-consumo-insumo-custo-industrializacao.md`,
seção 3.2.

## Pontos de extensão conhecidos

- Telas de cadastro do Envase em si (além do CRUD padrão gerado) ainda
  não foram desenhadas — pendência registrada em `01-visao-geral.md`.
- Nenhuma tela própria pra `calcular_custo_industrializacao_envase()`
  ainda — só a função de service (ver UC03, `05-casos-de-uso.md`).
- FK real pra `BrewSession` (`feature_mash_control`) já existe
  (`lote_id`) — cross-Feature dentro do mesmo Addon é permitido pela
  skill 02, então isso não precisa de referência fraca.
- Camada de precificação de venda (% lucro/margem/impostos em cima do
  custo de industrialização) é extensão futura registrada, fora de
  escopo — ver skill 26, seção 4.
