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

`Envase.componentes_snapshot` guarda a fotografia da composição e das
saídas no registro. A preparação de novos envases consulta o cadastro via `material_lookup.get_composicao(material_resultante_id)`
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

- Preparação de novos envases integrada ao workspace (2A.1); registro e
  estorno ainda continuam pelos fluxos próprios existentes.
- A nova prévia calcula embalagem prospectiva, sem substituir o custo
  histórico de `calcular_custo_industrializacao_envase()` nem a precificação.
- FK real pra `BrewSession` (`feature_mash_control`) já existe
  (`lote_id`) — cross-Feature dentro do mesmo Addon é permitido pela
  skill 02, então isso não precisa de referência fraca.
- **Camada de precificação de venda — implementada**: a skill 26,
  seção 4, registrava isso como extensão futura fora de escopo; foi
  implementada numa sessão posterior (`precificacao_service.py`,
  `CalculoPrecificacao`/`ItemCustoIngrediente`, ver `04-modelo-de-dados.md`
  e `03-fluxos.md`) — nota desatualizada nesta auditoria de
  documentação.

## Pendência real encontrada nesta auditoria: `ItemEnvase` congelado afeta o custo de embalagem da Precificação

`precificacao_service._calcular()` soma o custo de embalagem a partir
de `ItemEnvase.query.filter_by(envase_id=...)` — mas
`envase_estoque_service.registrar_envase()` **parou de inserir** nessa
tabela desde a skill 26 (ver seção acima, "`ItemEnvase` — decisão de
remoção física"). Resultado prático: para qualquer Envase criado
depois da skill 26, `custo_embalagem_total` calculado pela
Precificação vem sempre `0.0`, mesmo que o Material resultante tenha
Composição completa e custo real em `Saldo`. Duas correções possíveis,
nenhuma decidida ainda:

1. `precificacao_service` passa a ler a Composição do Material
   resultante do Envase (mesma fonte que
   `calcular_custo_industrializacao_envase()` já usa), em vez de
   `ItemEnvase`.
2. `ItemEnvase` volta a ser populado (reverteria parte da decisão da
   skill 26).

Registrado aqui como achado de auditoria — nenhuma das duas foi
aplicada nesta sessão (é mudança de código, não de documentação).

## Extensão manual: preparação no workspace (2A.1)

`services/envase_preparation_service.py` reutiliza volume do serviço manual
de registro e os lookups públicos do estoque; não chama serviços gerados.
O controller manual `feature_mash_control/controller/plant_workspace.py`
valida permissões/contexto e renderiza `_envase_preview.html`. A entrada
`_envase_preparation.html` fica no card do lote, com combo padrão e GET AJAX.
Não grava estado e não introduz caminho paralelo de baixa. A consulta não
recalcula o custo confirmado do lote nem aplica margens/impostos.

Registro 2A.2 precisa de idempotência no servidor e continuidade de custos;
não basta desabilitar botão. A precificação existente ainda usa `ItemEnvase`
para embalagem e recalcula insumos da receita; conferir snapshots/custo
confirmado antes de tratar o processo como consolidado. O estorno 2B já tem
serviço transacional, mas o retorno/detalhe local ainda precisa ser integrado.

Entrega e testes: [2A.1](../../../../../../docs/patches/workspace-preparacao-envase.md).

## Registro pelo workspace (2A.2)

Envase.idempotency_key é opcional e protegida por índice único; recebida
via confirmação assinada da prévia. A reserva precede baixas na transação
central, e repetição recupera o registro sem repetir consumo/log. Rollback
remove a chave de tentativas malsucedidas. Os callers sem chave continuam
funcionando; não editar o service gerado. Migration e testes na raiz:
`docs/patches/workspace-registro-envase-2a2.md`.


## Precificação 2C.1 — base histórica

O motor manual escolhe a fonte: `insumos_baixados_em` determina uso do total
`custo_total_insumos` congelado (zero válido, null bloqueado); a ausência de
snapshot de embalagem permite apenas fallback estimado dos ItemEnvase
legados. Snapshot preenchido/vazio é autoritativo, sem ler a composição ou
preço atual. `origem_preco=registrado` cabe no String(20) existente e sua
annotation enum foi ampliada; não há migration.

As flags de origem/incompletude são metadados da resposta atual, não novas
colunas nem inferências sobre cálculos antigos. Totais e linhas registrados
na precificação continuam persistidos nos campos existentes. Não fabrica
linhas de ingrediente históricas: o lote só tem total congelado disponível.
Valores já salvos não são recalculados ao vincular/cancelar envase. Vincular
valida lote, status, exclusão e impede troca de vínculo existente.
O motor usa os getters públicos do estoque para saldo/unidade-base/material.
Controller/API/tela de precificação são manuais, não gerados pelo CrudGen.
