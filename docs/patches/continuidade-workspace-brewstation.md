# Continuidade do workspace BrewStation

Planejamento técnico de 30/09/2026, conferido no commit `b3d3bab`.
Este documento registra cobertura e próximos incrementos; itens planejados
não são funcionalidades implementadas. O planejamento inicial não alterou
banco, menus ou runtime; os incrementos abaixo registram a evolução real.
Na análise inicial de 30/09, os testes recentes haviam sido aprovados pelo
usuário; não foi executado pytest nem feita validação visual naquela análise.
Os incrementos abaixo registram as execuções posteriores e pendências locais.

## Estado verificado

| Etapa | Estado da integração | Evidência e lacuna real | Próximo incremento | Dependências |
| --- | --- | --- | --- | --- |
| Planta, tanques e mapeamentos | Parcial | `plant_workspace.py` tem criação/edição e validações; manutenção completa ainda depende de cadastros | Inventariar lixeira, restauração e configuração avançada antes de ocultar acessos | Permissões, pertencimento e funcionalidades dos cadastros |
| Receita e ingredientes | Parcial | `_tab_recipe_detail.html` reúne conferência/custo, vínculo local, revisão e dados planejados; cadastro avançado preservado | Preservar proteção de receitas usadas; operações adicionais na etapa 4 | Serviço de resolução, conversão, referências públicas e proteção de receitas usadas |
| Sessões, histórico e alarmes | Concluída no escopo dos patches recentes | Busca/paginação, edição básica, confirmação de insumos e reconhecimento rastreável estão no código | Preservar; operações adicionais ficam na etapa 4 | Suítes de workspace, runtime e estoque |
| Envase e precificação | Parcial | Prévia/registro na aba; detalhes/estorno 2B validados; custos e rateio 2C.1/2C.2 validados | 2C.1/2C.2 validados; etapas avançadas restantes | Saneamento, composição, snapshots e transação de estoque |
| Dashboards | Parcial | Seleção/criação/edição básica, fundo/padrão e manutenção 3B implementados; standby sem runtime | 3A.1/3B validados; 3A.2: definir standby | Widgets/tubulação existentes e limpeza de listeners/timers |
| Etapas e automação | Parcial | Timeline e geração já integradas; Automação tem filtros, edição/manutenção; sessões têm controles e ajustes no patch combinado | 4B.3/4B.4/4C aprovados nos testes pelo usuário; inventário avançado permanece | Runtime existente, permissões e escopo global/por sessão |
| Menus | Parcial | Sete códigos configurados no comando de ocultação; não prova cobertura de toda manutenção | 5: matriz revisada; manter sete ocultações e preservar manutenção externa | Validação funcional dos incrementos anteriores |
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
  autenticada, permissão, combo padrão e retorno à seleção. Aplicado e
  validado pelo usuário.
  Ver [interface 1B](workspace-saneamento-ingredientes-interface.md).
- 1C: revisão completa e dados planejados de ingredientes aplicados e
  validados pelo usuário em 01/10/2026.
  Ver [revisão e dados — 1C](workspace-revisao-receita-ingredientes.md).
- 2A.1: preparação de envase e prévia de embalagens implementadas,
  aplicadas e validadas pelo usuário. Não registra envase nem baixa estoque.
  Ver [preparação — 2A.1](workspace-preparacao-envase.md).
- Correção intermediária: seletores e layout implementados; validação local pendente.
  Ver [inventário e testes](brewstation-seletores-layout.md).
- 2A.2 (registro): suíte funcional passou; correção das migrations validada localmente.
- 2B (detalhes/estorno): validado pelo usuário. 2C.1 (custos registrados) e 2C.2 (rateio): validados pelo usuário; etapas 3–6 permanecem pendentes.
  As proteções locais não alteram o comportamento
  do de-para global, dos importadores ou das ações avançadas do CRUD/runtime.

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
5. Achado original corrigido no 1C: `criar_nova_versao()` agora copia
   volume, ingredientes/especificações, timeline, água e fermentação ativos.
   Remapeia referências internas e grava snapshot completo; não copia lotes
   nem seus custos. Referência a pai/ingrediente externo ou apagado bloqueia
   a revisão com rollback. Históricos anteriores não são reescritos.
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

2A.1 integra produto resultante/litros e prévia de composição, unidades físicas
e estimativa das embalagens no contexto do lote. É leitura, sem gravação,
reserva, confirmação de ingredientes ou rateio do custo do lote. Componentes
repetidos são somados para avaliar necessidade/saldo. Custos ausentes
permanecem identificados; composição vazia gera estimativa incompleta.

2A.2 integra a confirmação explícita via `registrar_envase()`; suíte funcional
aprovada e correção das migrations validada pelo usuário. Ver [registro 2A.2](workspace-registro-envase-2a2.md).
O fallback dos insumos é informado antes da confirmação e protegido pela
permissão de atualizar o lote. A repetição do token é protegida por chave
única persistente; a reserva de escrita e o log compartilham a transação.

A continuidade da precificação permanece pendente: o serviço atual ainda
lê `ItemEnvase` para embalagem, sem usar snapshots dos envases novos; o
cálculo dos insumos deve preservar custo confirmado. A prévia não usa esse
motor de preço de venda nem representa sua consolidação.

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

## Retorno dos testes de seletores/layout

Execução local: 427 passed, 2 failed, 627 warnings. As duas expectativas de
nomes de painéis no HTML inicial foram ajustadas para a API do combo; avisos
Query.get() dos pontos manuais indicados foram tratados. Validação da correção
pendente. Ver [roteiro](brewstation-testes-combos-sqlalchemy.md).

## Validação das correções e entrega 2A.2

Usuário confirmou a correção da fixture RBAC; testes dos combos também
passaram na execução curta. O registro integrado de envase foi implementado
com confirmação padrão, token contextual e chave única persistente. Exige
migration; validação do incremento funcional ainda pendente. 2B/precificação
e demais etapas não são consideradas concluídas.


## Retorno da suíte após 2A.2 — 02/10/2026

Execução local informada pelo usuário: **498 passed, 2 failed, 2 warnings**.
Os fluxos funcionais da seleção executada passaram; a validação global ainda
pendia da suíte de migrations. O head falso era causado pelo parser regex do
teste (aspas duplas ignoradas), e o downgrade pressupunha nomes de constraints
históricas em esquema criado pelos models. Correção e comando focado em
[migrations-downgrade-testes.md](migrations-downgrade-testes.md).
O aviso de `slow` foi corrigido com registro da marca, sem ocultar warnings.
2B/precificação e etapas seguintes permanecem pendentes.


## Incremento 2B — detalhes e estorno do envase

A correção da suíte de migrations foi validada pelo usuário. O 2B incorpora
consulta contextual de snapshots e estorno com motivo/confirmador padrão,
retorno ao mesmo lote, RBAC, pertencimento e log na transação do serviço.
Não exige migration. Validação local do 2B pendente; roteiro em
[workspace-envase-detalhes-estorno-2b.md](workspace-envase-detalhes-estorno-2b.md).
Precificação alinhada aos snapshots, dashboards avançados e demais etapas
continuam pendentes; não ocultar novos menus por esta entrega.


## Incremento 2C.1 — base de custo na precificação

2B passou nos testes locais informados pelo usuário. Este incremento trata
o uso de ingredientes congelados e snapshots de embalagem na precificação,
sem movimentar estoque ou inventar detalhamento histórico. Retorno contextual
por lote/envase e validação de vínculos/status. Sem migration. Ver
[precificacao-custos-registrados-2c1.md](precificacao-custos-registrados-2c1.md).
O cálculo mantém o escopo de ingredientes do lote completo; consolidação de
rateio por envase/unidade permanece para 2C.2. Não considerar toda a etapa
de precificação concluída nem ocultar menus por este patch.

## Incremento 2C.2 — rateio e preço por unidade

Implementado: ingredientes proporcionais aos litros registrados ativos,
embalagens do envase escolhido, preço/custo por unidade e preço por litro.
Snapshot de produção no registro e snapshot da base na precificação salvam
a origem e evitam reconstruir o histórico com cadastros posteriores.
Denominador muda para novos cálculos após registro/estorno; salvos preservados.
Requer migration `f8c214ab709e`; sem backfill. Unidades antigas estimadas ou
indisponíveis ficam identificadas. Sem preço unitário do lote sem envase.
Entrega: [precificacao-rateio-unidade-2c2.md](precificacao-rateio-unidade-2c2.md).
Validação visual/local pendente; não considerar demais etapas concluídas.

## Incremento 3A.1 — fundo e painel padrão

Implementados cor/imagem de fundo e padrão por planta, em formulário próprio
no workspace. A imagem passa a ser renderizada também na view própria, atrás
de widgets e tubulação, sem capturar eventos. Sanitização de cor/URL na
escrita e leitura; legados inválidos não são gravados durante consulta.
Padrão substitui somente outros layouts não apagados da mesma planta, na
mesma transação. Sem padrão, permanece fallback para o primeiro cadastrado.
O acesso global continua resolvendo seu padrão disponível; não foi criada
nova configuração global nem migrados padrões antigos. CRUD avançado pode
ter padrões duplicados; esta ação os consolida na planta escolhida.

Sem migration. Retorno normal e AJAX preservam o painel editado.
Standby tem campos no model, sem runtime encontrado: 3A.2 deve definir e
implementar o comportamento antes de expor controle funcional.
3B (lixeira/restauração), etapas 4–6 e validações locais 2C.1/2C.2 continuam
pendentes; pedido de continuidade não foi interpretado como aprovação visual.
Entrega: [workspace-dashboard-fundo-padrao-3a1.md](workspace-dashboard-fundo-padrao-3a1.md).

## Incremento 3B — lixeira e restauração locais

Implementada manutenção do painel selecionado e lixeira paginada da planta,
com 20 itens/página (`trash_page`). Disponível também quando não há painel
ativo, permitindo recuperar o último removido. Modal padrão via catálogo
i18n e ações POST autenticadas com permissões existentes trash/restore.

`dashboard_workspace_actions.maintain_layout` reaproveita o serviço gerado
sem editá-lo; valida planta/painel, estado e reverte falhas de gravação.
Widgets e demais configurações preservados. Restauração de antigo padrão
não desmarca padrão ativo: retorna como não padrão se houver outro; sem
padrão atual, preserva o flag original. Remoção não promove novo padrão;
a seleção segue fallback existente. Seleção explicitamente inválida segue
404, sem troca silenciosa. Retorno normal/AJAX recebe seleção adequada e
limpa o dashboard pelos helpers existentes.

Sem migration, exclusão permanente, menu novo ou alteração de controles/
sessões/estoque. Standby 3A.2 continua exigindo definição; etapas 4–6 e
validação local dos incrementos recentes continuam pendentes.
Entrega: [workspace-dashboard-lixeira-restauracao-3b.md](workspace-dashboard-lixeira-restauracao-3b.md).


### 05/10/2026 — Validação anterior e Automação 4B.1

O usuário confirmou as etapas anteriores como aplicadas e validadas:
2C.1, 2C.2, 3A.1 e 3B. Essa confirmação atualiza os apontamentos históricos
de validação pendente acima. Standby 3A.2 não foi implementado.

4A: inventário dos controles de sessões/etapas registrado em
[workspace-automacao-historico-4b1.md](workspace-automacao-historico-4b1.md).
4B.1: filtros e paginação de 20 regras e disparos implementados; histórico
exige `automation_rule_logs.list`. Consulta não aciona dispositivos.
A seleção explícita de regra externa/apagada/inválida devolve erro.

Achado para revisão antes de 4B.2: o motor atual filtra por sensor e regra
ativa, sem restringir execução pelo `session_id`. Vínculo de cadastro não
é isolamento de execução. Logs não possuem planta/sessão de origem.
Criação/edição seguem no CRUD; não fechar a etapa 4 nem ocultar seus menus.
Validação deste novo patch permanece pendente; não há migration.


### 05/10/2026 — 4B.1 validado e guarda 4B.2a

O usuário validou filtros/paginação/histórico 4B.1. Novo patch 4B.2a implementa
restrição de novos disparos por sessão ativa e planta disponível; globais
preservam comportamento. Isso substitui a ausência de guarda descrita acima.
Não desliga atuadores nem define isolamento físico por mapeamentos.
Sem migration; testes locais do usuário pendentes. Ver
[workspace-automacao-execucao-4b2a.md](workspace-automacao-execucao-4b2a.md).
Criação/edição/ativação local, proveniência do sensor, standby e menus permanecem
pendentes; etapa 4 não está encerrada.


### 05/10/2026 — Isolamento de configuração 4B.2b

4B.2a foi entregue; sua validação ainda não foi informada explicitamente.
4B.2b implementa guarda de mapeamento exclusivo e ator único para regras
vinculadas. Evento continua por nome/valor: não é autenticação de origem física.
Ver [roteiro 4B.2b](workspace-automacao-isolamento-4b2b.md). Sem migration;
validação local pendente. Edição/ativação, standby e menus continuam pendentes.


### 05/10/2026 — Entrega combinada 4B.3 / 4B.4 / 4C

Por solicitação do usuário, estas frentes passam a ser entregues juntas para
uma única rodada local de testes. Implementados: criação/edição inativa de
regras, ativação/desativação, lixeira/restauração sem reativação, paginação da
lixeira, controles contextualizados de sessão e ajuste auditado de etapa.
GET permanece consulta; mutações exigem permissões próprias e modal do Core.

Operações de sessões delegam ao runtime existente após validar planta/sessão,
status e estado esperado da tela. Não foram duplicados timers/motores/estoque.
Ajuste usa serviço de timeline existente e registra operador; receita e campos
não ajustáveis permanecem preservados. Ver
[workspace-automacao-sessoes-consolidacao-4b3-4c.md](workspace-automacao-sessoes-consolidacao-4b3-4c.md).

Sem migration. Nova entrega ainda precisa de validação do usuário. Não presume
validação separada dos patches 4B.2a/4B.2b. Permanecem: revisão de proveniência
física de eventos, exclusão permanente no cadastro avançado, PID contínuo,
standby 3A.2, eventual manutenção adicional de sessões e revisão dos menus.


### 05/10/2026 — Patch combinado validado e revisão de menus

Usuário informou aprovação dos testes do patch combinado 4B.3/4B.4/4C.
Isso atualiza sua pendência histórica de validação acima, sem afirmar testes
separados dos incrementos de execução. Revisão de navegação mantém sete
ocultações: candidatos adicionais ainda têm manutenção externa. Novo acesso
à aba Automação e identificação dos cadastros avançados/global. Sem migration.
Ver [matriz e roteiro](workspace-revisao-menus.md). Este novo patch aguarda
validação local. Standby e auditoria integrada continuam próximos trabalhos.


Correção de apresentação dos menus: nomes curtos preservados; description
exibida como tooltip Bootstrap no menu lateral. Sem migration. Roteiro em
`docs/patches/workspace-menu-hints.md`.


Ajuda de Função do dispositivo na aba Planta transferida para ícone com
tooltip hover/foco e limpeza AJAX. Cores explícitas para hints nos temas.
Sem migration; ver docs/patches/workspace-planta-hint-contraste.md.
