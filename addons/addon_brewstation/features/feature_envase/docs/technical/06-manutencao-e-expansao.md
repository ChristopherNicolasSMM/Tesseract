# 06 — Manutenção e Expansão (Feature Envase)

## Adicionar um campo a `Envase`/`ItemEnvase`

1. Editar `model/envase.py` (ou `item_envase.py`).
2. `python run.py generate --model addons/addon_brewstation/features/feature_envase/model/envase.py --addon brewstation --feature envase --overwrite`
3. Hooks (`*_hooks.py`) preservados automaticamente.

## Resolver a pendência de bloqueio por saldo insuficiente

Mesma pendência em aberto do `addon_estoque` (ver
`addons/addon_estoque/docs/technical/05-casos-de-uso.md`, UC-02):
hoje um Envase pode ser registrado mesmo sem saldo suficiente de
embalagem — o sistema não bloqueia, só seria coerente decidir os dois
juntos (Movimentação de saída e Envase chamam o mesmo caminho de baixa
de estoque).

## Como o Envase dá baixa no estoque (sem tabela própria de material)

`Envase`/`ItemEnvase` não guardam nenhum dado de catálogo de
embalagem — isso é 100% `addon_estoque` (`Material` categoria
`"embalagem"`). Ao salvar um Envase, o service desta Feature chama o
service público de `addon_estoque` (referência fraca + chamada
síncrona, nunca FK/ORM direto) pra lançar a Movimentação de saída
correspondente. Se um dia precisar mudar essa baixa de síncrona pra
assíncrona (ex.: processamento em lote), o ponto de entrada é esse
mesmo service, não o model.

## Pontos de extensão conhecidos

- Telas de cadastro do Envase em si (além do CRUD padrão gerado) ainda
  não foram desenhadas — pendência registrada em `01-visao-geral.md`.
- FK real pra `BrewSession` (`feature_mash_control`) já existe
  (`lote_id`) — cross-Feature dentro do mesmo Addon é permitido pela
  skill 02, então isso não precisa de referência fraca.
