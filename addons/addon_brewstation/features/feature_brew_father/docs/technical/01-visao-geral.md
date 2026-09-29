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

## Sincronização seletiva (skill 27, 2026-09-01)

Além de `sync_recipes()` (importa tudo de uma vez), existe um segundo
caminho: `listar_receitas_disponiveis()` — listagem enxuta (sem
detalhe por receita) cruzada com `MashRecipe.origem_receita_id` já
conhecidos, sinalizando cada uma como nova/já importada/apagada
(pendente de reimportar) — e `sincronizar_selecionadas(origem_ids)`,
que busca o detalhe completo só das marcadas. Motivo: a API do
BrewFather não expõe filtro por tag/pasta no servidor (`GET /v2/recipes`
só aceita `include`/`complete`/paginação/`order_by`), então o filtro
precisa acontecer no Tesseract. Ver `03-fluxos.md` e
`docs/skills/27-proposta-sincronizacao-seletiva-brewfather.md`.

`brewfather_client.py` foi dividido em `list_recipes_basico()`
(listagem crua, sem normalizar) + `get_recipe_normalizado()` (detalhe
de uma receita, já normalizado) — `get_recipes()` (usado por
`sync_recipes()`) hoje é só a composição dos dois, não duplica mais a
lógica de normalização.

## Portal de sincronização (skill 28)

`/brewstation/brewfather-syncs/portal` é a entrada operacional para
consultar até 500 receitas paginadas, solicitar `include=path,tags`,
filtrar localmente por nome, estilo, tipo, situação, pasta ou tag e
importar ou ressincronizar até 50 selecionadas por operação. A ação
geral de ressincronização usa os IDs de todas as receitas importadas
ativas e cria versões novas (até 500 por operação); a ação de remoção
move todas as receitas de origem Brewfather para a lixeira local,
preservando lotes e histórico. O histórico
gerado pelo CrudGen continua em `/brewstation/brewfather-syncs`;
o atalho da barra leva ao portal. Abas de lotes e inventário permitem
consulta e filtros com escopos `batches.read` e `inventory.read`,
respectivamente; ainda não importam esses registros. A regra de saldo do estoque exige conciliação via ledger
antes de qualquer sincronização de quantidade externa.

## Prévia de conciliação de inventário

Fermentáveis e lúpulos aceitam vínculo explícito por ID do item remoto
e ID de Material, gravado em `BrewfatherInventoryLink` (migration
`6abac6de2f17`). `IngredientMapping` fornece apenas sugestão pelo nome;
as duas associações não são fundidas. O portal compara saldo via
`material_lookup.get_saldo()` e unidade base via
`material_lookup.get_unidade_base()`, convertendo KG↔G e bloqueando
unidades não definidas. A prévia não escreve no Brewfather nem altera
`Saldo`/`Movimentacao` no Tesseract.

## Pendências reais

- Item (c) do `BACKLOG.md` — adjuntos (`miscs[]`) e água (`water`) da
  API BrewFather, decidido mas não implementado.
- `i18n/pt_BR.json` — não escrito (gap conhecido em quase todo o
  Addon, registrado em `BACKLOG.md`).

## Autocadastro de unidades-base

Ao cadastrar automaticamente um ingrediente, o serviço também cria a
unidade-base do Material quando a unidade da linha de receita é
reconhecida no catálogo (KG, G, MG, L, ML, UN ou PCT para `pkg`).
O fator é 1 e o Material permanece pendente de revisão. Um Material
reaproveitado com base existente preserva a configuração manual.
Unidades desconhecidas exigem revisão, pois não é seguro inferir o
conteúdo de uma embalagem. PCT identifica a embalagem; o fator de
conversão é definido em cada Material.
