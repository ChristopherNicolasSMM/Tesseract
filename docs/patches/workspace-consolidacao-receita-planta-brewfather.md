# Consolidação de receita, planta e continuidade Brewfather

Pacote único sobre `59c33a8`, reunindo as três frentes autorizadas. Aplicado e
validado localmente pelo usuário, conforme confirmação de abertura da fase 3
em 07/10/2026. Auditoria/correção YeastBank e integridade do recebimento também
foram entregues e validadas. Ver [estado da fase 3](fase3-inventario-e-sequencia.md).

## Preparação da receita

Na aba Receita é possível editar nome, descrição e volume planejado; criar,
editar, enviar à lixeira e restaurar etapas de fermentação e perfis de água.
Os campos são os existentes nos modelos. Valores numéricos inválidos, negativos
fora dos limites e contextos desconhecidos são rejeitados. O contexto de água
não muda na edição; um contexto existente na lixeira deve ser restaurado.

Qualquer lote vinculado, inclusive apagado ou concluído, bloqueia essas
alterações. Use **Criar revisão** e trabalhe na nova receita. Os lotes anteriores
continuam com sua receita, etapas e custos. Cada alteração efetiva grava o
snapshot completo e o usuário autenticado em RecipeHistory na mesma transação;
falha no snapshot desfaz a alteração. Repetição sem alteração não duplica histórico.

## Manutenção da planta

A aba Planta oferece lixeira/restauração de tanques e mapeamentos, com páginas
de 20 registros e permissões próprias de trash/restore. Não existe cascata:
remova primeiro os mapeamentos; restaure primeiro o tanque. Pertencimento à
planta é validado no servidor.

Sessões não apagadas em draft/active/paused bloqueiam a manutenção. Tanques
referenciados em widgets (inclusive apagados), etapas históricas ou tubulações
não são enviados à lixeira. Mapeamentos usados por widgets ativos, tubulações
ou regras ativas também são bloqueados. Restauração valida função, categoria e
duplicidade de papel no tanque. Nenhuma dessas operações comanda dispositivos.

A revisão dos menus mantém os sete códigos atuais do comando
`hide-legacy-mash-control-menu`. Tanques, mapeamentos, água e receitas continuam
com acessos globais/avançados: exclusão permanente e administração global não
foram substituídas pelo fluxo local. Não há alteração automática de visibilidade.

## Brewfather

O atalho na aba Receita abre o portal com `workspace_plant_id`, validado por
permissão e existência da planta. Filtros e navegação principal preservam esse
contexto. Importação de uma receita retorna à aba Receita da mesma planta com
seu ID local; grupos e erros retornam ao portal contextual. Nenhuma URL livre
é aceita como destino. Cadastros auxiliares, histórico e conciliação avançada
continuam com sua navegação própria.

Ressincronizar cria uma nova versão remota e preserva as versões anteriores
sem enviá-las automaticamente à lixeira. Quantidades, unidades, etapas e água
locais permanecem na versão antiga; a nova recebe o plano remoto. Não há fusão
silenciosa desses valores. Descrição, volume planejado e configuração de
equipamento são conservados porque o normalizador atual não fornece esses dados.

Vínculo local ou decisão Não consumir é reaproveitado apenas com correspondência
única por descrição/tipo/uso. Duplicatas com decisões locais ficam pendentes; material inexistente ou
inativo exige novo saneamento. Conversões continuam no cadastro do material,
sem regravação. A nova versão tem snapshot de importação com origem rastreável.
Renomear a receita remota mantém a progressão das versões. Uma falha desfaz a
nova versão e preserva a anterior. Exclusão em massa que inclui receita com
lote é recusada integralmente.

Consultar, editar planejamento, restaurar configuração e importar não movimentam
estoque. Consumo continua em `confirmar_consumo_ingredientes`; custos congelados,
snapshots de envase e estornos não são alterados.

## Aplicar e testar

**Sem `db upgrade`: não há migration nem alteração de schema.**

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-consolidacao-receita-planta-brewfather.patch
python -m pytest tests/test_workspace_cycle_consolidation.py tests/test_plant_workspace.py tests/test_feature_brew_father.py tests/test_recipe_timeline.py tests/test_dashboard_runtime.py tests/test_hide_legacy_mash_control_menu.py -q
node tests/js/test_workspace_preparation.cjs
```

Para regressão ampliada de estoque/envase, se desejado:

```powershell
python -m pytest tests/test_feature_envase.py tests/test_precificacao_envase.py tests/test_addon_estoque.py -q
```

## Rotas e roteiro visual

1. `/brewstation/plant-workspace/<PLANTA>?tab=recipe&recipe_id=<RECEITA>`:
   numa receita sem lotes, editar os dados gerais; adicionar fermentação e água;
   editar, enviar à lixeira e restaurar. Cancelar o modal deve preservar dados.
   Conferir histórico e os cinco contextos de água com select padrão.
2. Abrir uma receita usada por lote antigo: formulários ficam bloqueados.
   Criar revisão, editar a nova e conferir que o lote continua na receita anterior.
3. `/brewstation/plant-workspace/<PLANTA>?tab=plant`: num tanque sem referências,
   enviar mapeamento e tanque à lixeira; restaurar na ordem inversa. Conferir
   paginação. Testar os bloqueios de sessão aberta, widget, etapa, tubulação e regra.
   Conferir que outra planta não aceita o ID desse registro.
4. Na aba Receita, abrir **Portal Brewfather**. Conferir
   `/brewstation/brewfather-syncs/portal?workspace_plant_id=<PLANTA>` e o retorno.
   Ressincronizar uma receita com ajustes locais; comparar as versões, vínculos,
   conversões e o lote anterior. Sem cadastro/API configurada, testes automatizados
   usam respostas simuladas e não comprovam a integração remota real.
5. Com usuário limitado, conferir botões e recusas de criação, edição, lixeira e
   restauração. Conferir mensagens e contraste nos temas disponíveis.

As rotas POST de preparação ficam em
`/brewstation/plant-workspace/<PLANTA>/recipes/<RECEITA>/preparation/<KIND>/<ACTION>`
e na variante com `<ROW_ID>` antes da ação. KIND: recipe/fermentation/water;
ACTION: save/trash/restore (dados gerais usam apenas save).
Manutenção: `/brewstation/plant-workspace/<PLANTA>/maintenance/<KIND>/<ID>/<ACTION>`;
KIND: vessels/mappings; ACTION: trash/restore.

## Verificação da entrega

Executado neste ambiente com dependências de validação: 474 casos das suítes
existentes de workspace, Brewfather, timeline, runtime e menus aprovados.
A rodada ampliada teve uma falha na fixture nova (campo inexistente no modelo);
a fixture foi corrigida e a suíte final de consolidação foi reexecutada inteira:
**50 passed**. Não há falha restante nesses casos. Os três comandos JavaScript
(preparation, operations e weak_ref_combo) também passaram.
Sintaxe Python/JSON/Jinja e git diff --check conferidos.
Testes de estoque/envase/precificação não foram reexecutados neste pacote;
os comandos opcionais acima ficam disponíveis para regressão local ampliada.
A integração Brewfather real e a aparência nos temas aguardam teste visual local.
