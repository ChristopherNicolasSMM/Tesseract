# Continuidade do workspace BrewStation

Planejamento técnico de 30/09/2026, conferido no commit `b3d3bab`.
Este documento registra cobertura e próximos incrementos; itens planejados
não são funcionalidades implementadas. Não altera banco, menus ou runtime.
Os testes recentes foram aprovados pelo usuário; nesta análise não foi
executado pytest nem realizada validação visual em uma aplicação em execução.

## Estado verificado

| Etapa | Estado da integração | Evidência e lacuna real | Próximo incremento | Dependências |
| --- | --- | --- | --- | --- |
| Planta, tanques e mapeamentos | Parcial | `plant_workspace.py` tem criação/edição e validações; manutenção completa ainda depende de cadastros | Inventariar lixeira, restauração e configuração avançada antes de ocultar acessos | Permissões, pertencimento e funcionalidades dos cadastros |
| Receita e ingredientes | Parcial | `_tab_recipe_detail.html` reúne conferência/custo; cada ingrediente abre `recipe_ingredients.detail` em outra página | 1A/1B: resolução segura e vínculo local; 1C: demais dados | Serviço de resolução, conversão, referências públicas e proteção de receitas usadas |
| Sessões, histórico e alarmes | Concluída no escopo dos patches recentes | Busca/paginação, edição básica, confirmação de insumos e reconhecimento rastreável estão no código | Preservar; operações adicionais ficam na etapa 4 | Suítes de workspace, runtime e estoque |
| Envase e precificação | Parcial | Lista e retorno ao lote integrados; registro/estorno existem nos serviços/hooks, fora da aba | 2A: preparação/registro; 2B: detalhes/estorno com retorno | Saneamento, composição, snapshots e transação de estoque |
| Dashboards | Parcial | Seleção/criação/edição básica integradas; fundo, standby, padrão e manutenção usam cadastro completo | 3A: opções avançadas; 3B: manutenção | Widgets/tubulação existentes e limpeza de listeners/timers |
| Etapas e automação | Parcial | Timeline e geração já integradas; Automação lista regras e últimos 20 logs, com criação/edição no CRUD | 4A: inventário de operações; 4B: incremento das regras e histórico | Runtime existente, permissões e escopo global/por sessão |
| Menus | Parcial | Sete códigos configurados no comando de ocultação; não prova cobertura de toda manutenção | 5: matriz de cobertura e ocultação seletiva | Validação funcional dos incrementos anteriores |
| Brewfather e YeastBank | Radar posterior | Portal Brewfather e painel YeastBank já existem; não reconstruir como novidades | 6: auditorias específicas e novas lacunas | Estabilização do fluxo prioritário |

Concluída nesta tabela significa o escopo explicitamente descrito, não toda
a área funcional. A quantidade final de patches pode mudar ao conferir dependências.

### Acompanhamento dos incrementos

- Planejamento: aplicado e validado pelo usuário.
- 1A: serviço local `ingredient_sanitation_service.sanear_ingrediente()`
  implementado e validado pelo usuário. Pytest não executado
  no ambiente do assistente (dependências indisponíveis).
  Ver [saneamento de ingredientes — 1A](workspace-saneamento-ingredientes-servico.md).
- 1B: vínculo local/Não consumir incorporados à aba Receita, com rota
  autenticada, permissão, combo padrão e retorno à seleção. Sintaxe/diff/
  aplicação verificados; pytest e teste visual aguardam validação local.
  Ver [interface 1B](workspace-saneamento-ingredientes-interface.md).
- 1C e etapas 2–6: pendentes. As proteções locais
  não alteram o comportamento do de-para global ou do CRUD atual.

## Achados que condicionam o saneamento

1. A receita é global. A planta no workspace preenche o destino da próxima
   sessão; não constitui propriedade da receita. A validação deve conferir
   planta existente, receita existente e `RecipeIngredient.recipe_id`, sem
   inventar vínculo exclusivo entre receita e planta.
2. `confirmar_mapeamento()` em `ingredient_resolution_service.py` atualiza
   o cache de-para e todos os ingredientes `pendente_depara` da mesma
   origem/descrição. A consulta não filtra ingredientes/receitas apagados
   nem receitas usadas por sessões. Também faz commit internamente.
   Chamá-lo diretamente para salvar uma linha local teria efeitos além
   da receita selecionada. Seus chamadores Brewfather devem continuar
   compatíveis ao introduzir proteção ou escopo explícito.
3. `confirmar_consumo_ingredientes()` consulta os ingredientes da receita
   atual do lote. `BrewSession` congela o custo total após confirmar, mas
   não possui uma cópia independente de cada ingrediente. Editar uma
   receita pode mudar um consumo futuro e a conferência exibida em lotes
   antigos. O custo já registrado não pode ser recalculado.
4. As etapas são copiadas por `generate_session_from_recipe()` para
   `BrewSessionStep`. A operação explícita `resync_session_steps()` ainda
   pode atualizar etapas pendentes; não tratar snapshots de etapas como
   proteção automática dos ingredientes.
5. `criar_nova_versao()` existe, mas não é uma clonagem completa do processo:
   não copia volume planejado, timeline, perfis de água e fermentação, nem
   todos os campos de especificação/uso dos ingredientes. Não usá-lo como
   solução completa de isolamento sem corrigir e testar essas lacunas.
6. A casca inicialmente só preservava `session_id`; o incremento 1B passou
   a propagar `recipe_id` ao abrir a aba Receita, preservando retorno/reabertura.

## Sequência de patches

### 1A — Serviço de saneamento com escopo e proteção

Primeiro incremento funcional recomendado. Antes de expor edição local:

- Definir uma operação manual limitada a uma receita e ingrediente.
  Material é confirmado pelos pontos públicos de `material_lookup`.
- Aceitar vínculo explícito e a decisão `ignorado` (Não consumir do estoque).
  Preservar descrição de origem e os demais campos fora desse incremento.
- Separar vínculo local de manutenção do de-para compartilhado. O padrão
  local não deve resolver ingredientes em outras receitas. Mudanças no
  cache exigem alcance explícito, permissões e proteção equivalentes.
- Proposta conservadora para o primeiro incremento: bloquear alteração
  local de receitas já referenciadas por sessões, com mensagem e orientação
  de revisão. Essa proteção é nova e deve ser documentada/testada; não
  está presente hoje. Uma revisão completa permitirá preparar nova receita
  sem mudar os lotes anteriores. Não mudar `recipe_id` de lote em silêncio.
- Conferir RBAC das ações de ingrediente e do cache separadamente. Usar
  `recipe_ingredients.update` na edição de linha e conferir as permissões
  existentes de `ingredient_mappings` antes de expor ações compartilhadas.
- Garantir transação/rollback, sem criar Material nem movimentar estoque.
  Não introduzir commit intermediário em uma operação composta.

Aceite: receita/ingrediente incompatíveis e registros apagados rejeitados;
material inválido rejeitado; nenhuma outra receita alterada pelo vínculo
local; receitas protegidas preservadas; falha desfaz a tentativa; ledger,
saldo, custo registrado e estado dos lotes permanecem iguais.

Schema: não há necessidade identificada para vínculo/status local. Se a
proteção exigir snapshot novo, separar proposta e migration do incremento.

### 1B — Vínculo dentro da aba Receita

- Card/formulário local por ingrediente, `weakref-combo` com fonte
  `materials`, identificação do vínculo atual e ação Não consumir.
- Mostrar conversão/unidade incompatível e dados ausentes usando
  `conferir_ingredientes()` e `calcular_custo_insumos_receita()` existentes.
- Salvar pelo serviço 1A, preservar planta/receita e recarregar conferência
  e estimativa com os helpers AJAX atuais. Bloquear envio duplicado na UI.
- Usar mensagens do Core e confirmação padrão para decisões de exclusão
  do consumo ou ações compartilhadas. Manter o cadastro avançado acessível.
- Não declarar que vincular resolve quantidade ou unidade incompatível;
  essas pendências continuam visíveis até o incremento 1C.

Aceite visual: navegar Sessões → Receita, corrigir vínculo em receita
editável e permanecer no contexto; cancelar ações preserva dados; combos
carregam via API; conferência/custo refletem o resultado; temas legíveis.

### 1C — Revisão completa e demais dados do ingrediente

Primeiro completar e testar a cópia de receita com ingredientes, volume,
timeline, água e fermentação para proteger receitas já usadas. Só então
expor revisão dessas receitas e edição de quantidade/unidade/uso/especificações.
Preservar campos externos, histórico e vínculo das sessões antigas. Não
inventar conversões de PCT para massa/volume; usar conversões cadastradas.
Alertas derivados da receita precisam ser conferidos após mudar uso/tempo
de lúpulo, sem alterar etapas executadas de sessões existentes.

Aceite: cópia integral, versão anterior intacta, custo confirmado intacto,
conversão validada e rollback da revisão completa. Confirmar consumo segue
como ação separada. Migration somente se houver mudança real de schema.

### 2A/2B — Envase e estorno a partir do lote

2A prepara produto resultante, composição, litros, embalagens e custos no
contexto do lote, com confirmação explícita via `registrar_envase()`. O
serviço atual pode confirmar insumos ainda não baixados como fallback;
essa consequência precisa aparecer antes de confirmar, não ao simular.
Verificar proteção de repetição do registro: o bloqueio de botão sozinho
não estabelece idempotência no servidor. Definir mecanismo se necessário
e conferir migration antes de implementá-lo.

2B apresenta snapshots e movimentações e integra `estornar_envase()` com
motivo, operador, modal padrão e retorno à mesma sessão. O hook atual
redireciona ao detalhe do envase. Estorno devolve os componentes registrados;
não presumir que desfaz consumo dos ingredientes ou a brassagem inteira.

Aceite: consulta/simulação não movimentam; falha de consumo/envase desfaz
toda a tentativa; repetição não duplica baixas; cancelamento não repete
devoluções; custos históricos usam snapshots; pertencimento/permissões
validados no servidor; sessões antigas mantêm retorno correto.

### 3A/3B — Dashboards avançados e manutenção

3A integra os campos existentes `background_color`, `background_image_url`,
`is_standby_enabled`, `standby_duration_seconds` e `is_default`. Conferir
semântica de painel padrão por planta versus acesso global antes de mudar
a exclusividade. Preservar widgets, dimensões, proprietário e runtime.

3B avalia lixeira/restauração e seleção após remover o painel atual, com
proteção de pertencimento e acesso fluido ao editor existente. Não recriar
widgets/tubulação nem ampliar ocultação de menus antes de cobrir manutenção.
Aceite: troca de aba limpa timers/listeners e não duplica polling; padrão
coerente; layouts externos/apagados rejeitados; widgets preservados.

### 4A/4B — Sessões, etapas e automação

Inventariar cada operação do runtime e das telas avançadas antes de propor
novo formulário. Avançar/voltar etapa, pausar/retomar, parar e ressincronizar
já têm rotas no `dashboard_runtime.py`. Evitar controles concorrentes.

Regras globais (`session_id` vazio) aparecem em mais de uma planta; deixar
esse alcance explícito. Avaliar criação/edição local e paginação/filtros do
histórico, que hoje se limita aos últimos 20 disparos. Conferir permissões
e semântica de ativação e preservar logs. Revisão de receita não deve
alterar sessão em execução automaticamente.

### 5 — Cobertura e menus

Criar matriz página antiga → operações cobertas → acesso avançado restante.
Manter os sete códigos atuais de `hide-legacy-mash-control-menu` até essa
revisão; não presumir inatividade real no banco a partir do catálogo.
Executar primeiro `flask hide-legacy-mash-control-menu --dry-run` no ambiente
do usuário. Ocultar menus apenas após validar cobertura; preservar rotas,
dados e `is_active` dos registros existentes na sincronização.

### 6 — Radar posterior, conferido antes de cada proposta

Brewfather já possui portal de receitas, pastas/tags, filtros, ações em
massa, lotes e inventário. `inventory_reconciliation_service.py` oferece
vínculo por ID remoto e prévia de saldos para fermentáveis/lúpulos; não
publica saldo no Brewfather. Publicação remota é uma etapa distinta a
especificar, com conversões e alcance explícitos. Não repetir o portal.

YeastBank já possui painel integrado. Fazer auditoria de usabilidade e
continuidade dos fluxos antes de escolher melhorias; este planejamento
não inclui nova auditoria completa desse addon nem execução com hardware/API.

## Validação e atualização contínua

Cada patch funcional registra aqui status real, commit, limites, migrations
e testes efetivamente executados. Atualizar também documentação técnica e
manual da funcionalidade alterada. Não marcar conclusão só por ter link para CRUD.

Suítes por frente (executar no ambiente adequado, sem usar banco fornecido
como alvo de escrita):

| Frente | Testes |
| --- | --- |
| 1A–1C | `test_plant_workspace.py`, `test_mash_control_ingredient_resolution.py`, `test_feature_brew_father.py`, `test_weak_ref_value_field.py`, `test_feature_envase.py`, `test_addon_estoque.py` |
| 2A/2B | `test_plant_workspace.py`, `test_feature_envase.py`, `test_addon_estoque.py` |
| 3A/3B e execução | `test_plant_workspace.py`, `test_dashboard_runtime.py`, `test_weak_ref_value_field.py` |
| 4/5/6 | Suítes existentes das operações efetivamente alteradas, identificadas no início do patch |

URLs para revisar o estado atual (substituir os IDs reais):

- `/brewstation/plant-workspace/`
- `/brewstation/plant-workspace/<ID_PLANTA>?tab=recipe&recipe_id=<ID_RECEITA>`
- `/brewstation/plant-workspace/<ID_PLANTA>/tab/recipe?recipe_id=<ID_RECEITA>` (fragmento AJAX)
- `/brewstation/plant-workspace/<ID_PLANTA>?tab=sessions&session_id=<ID_SESSAO>`
- `/brewstation/plant-workspace/<ID_PLANTA>?tab=dashboard`
- `/brewstation/plant-workspace/<ID_PLANTA>?tab=automation`
- `/brewstation/precificacao-envase/?lote_id=<ID_SESSAO>`

Entrega deste planejamento: patch documental gerado por `git format-patch`,
verificado com `git diff --check` e `git am --keep-cr` em checkout isolado
da base. Não precisa de `db upgrade`; não adiciona interface ou rota.
