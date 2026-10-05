# 06 — Manutenção e Expansão (Feature Mash Control)

## Sobre o motor de controle em tempo real (parcialmente portado)

O BrewStation original tinha PID controller, motor de automação
(avalia sensor continuamente) e scheduler de processo. Do que já foi
portado para o Tesseract:

- **Motor de automação: portado e ativo.** `AutomationRule` avalia de
  fato via EventBus do Core (`device_manager.actor.value_changed`) —
  é 100% orientado a evento, sem polling/scheduler, então não precisou
  esperar o sistema de Tasks. Ver `03-fluxos.md` e
  `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`, Fase E.
- **Loop de controle PID contínuo: ainda não portado.** As tabelas já
  têm os parâmetros necessários (`pid_kp`/`ki`/`kd` em
  `BrewSessionStep`), mas não existe nenhum processo consumindo esses
  parâmetros continuamente ainda — diferente do motor de automação
  (evento pontual), um PID de verdade precisa rodar em intervalos
  regulares. Candidato natural: `services/core/task_service.py`
  (sistema de Tasks/`APScheduler`, já existe e já é usado por outras
  áreas do Core — `/admin/tasks/`), não vale mais a justificativa
  antiga de "não temos scheduler ainda". Quando isso entrar, o motor
  consumiria as tabelas já existentes como configuração, sem precisar
  de migration nova.

## Dependência de `addon_device_manager`

Sempre ativar `device_manager` antes — `mash_control` declara isso em
`feature.json` (`"requires": ["device_manager", "estoque"]` — nome
correto do Addon promovido, skill 05; a Feature também depende de
`estoque` pra resolução de ingrediente de receita).

## Como adicionar um tipo de widget novo ao Dashboard

1. Adiciona o nome do tipo em `_VALID_WIDGET_TYPES`
   (`dashboard_runtime_service.py`) — sem isso, `create_widget_from_editor()`
   rejeita a criação.
2. Se o tipo precisa de dado em tempo real (como `step_card`), adiciona
   um branch em `get_layout_snapshot()` que popula
   `widgets_out[widget.id]`. Se é conteúdo estático (como `text`/`image`),
   não precisa — o dado vem direto de `config_json`, lido no template.
3. Bloco HTML novo no loop de widgets em `dashboards/view.html`
   (`{% elif w.widget_type == '...' %}`), e branch em JS
   `renderWidget()` se o tipo tiver dado dinâmico.
4. Ícone na paleta (`#dbPalette`, lista de tuplas
   `(widget_type, icone_bootstrap, label)` no topo do template).
5. Se o tipo precisa de vínculo (`vessel_id`/`device_function_name`),
   adiciona um `.db-panel-field` no painel lateral e inclui o tipo em
   `panelFieldsByType` (JS) — senão o painel não mostra os campos de
   configuração certos pra ele.

Nenhum desses passos precisa de migration — `DashboardWidget.widget_type`
é `String` livre e `config_json` é `JSON` livre; o "schema" de um tipo
de widget novo é inteiramente convenção de código, não de banco.

## Workspace consolidado por Planta (`plant_workspace.py`) — fragmento AJAX

Padrão novo (conversa — "juntar Dashboard + Etapas + Sessões + Planta
numa tela só"), fase 1: casca (`/brewstation/plant-workspace/` →
escolhe/cria Planta → `/plant-workspace/<id>` → barra de abas) + aba
Dashboard funcionando. As telas individuais de sempre continuam
existindo em paralelo — a remoção do menu é decisão pra depois de
validar o workspace na prática.

**Mecanismo de fragmento** (decisão da conversa: AJAX de verdade, não
iframe): `dashboards/view.html` foi dividido em `_content.html` (HTML)
+ `_scripts.html` (JS) — a tela cheia (`view.html`) inclui os dois
dentro de `{% block content %}`/`{% block extra_js %}`, sem mudar
nada de comportamento; um fragmento novo (`_fragment.html`) inclui os
mesmos dois partials sem `{% extends %}`, pra ser devolvido bruto por
`plant_workspace.tab_dashboard()` e injetado via `fetch()` na casca.

**Duas armadilhas resolvidas, valem pra qualquer aba nova**:
1. `<script>` injetado via `innerHTML =` não executa sozinho (o
   browser bloqueia por padrão) — a casca (`shell.html`) recria cada
   tag de `<script>` do fragmento recebido antes de confiar que ele
   rodou.
2. Se o fragmento tem algum polling (`setInterval`, como o Dashboard
   tem — snapshot a cada 3s), ele precisa de um jeito de "desligar" ao
   trocar de aba, senão fica rodando escondido pra sempre a cada
   reabertura. Convenção: o fragmento expõe `window.__tabCleanup =
   function () {...}` antes de terminar seu próprio `<script>`; a
   casca chama isso (se existir) antes de carregar a próxima aba.

**Como adicionar uma aba nova** (todas as 5 planejadas em conversa —
Dashboard, Sessões, Planta, Receita Mash, Automação — já
implementadas; segue como referência pra qualquer aba futura que
apareça):
1. Nova rota `GET /plant-workspace/<plant_id>/tab/<chave>` no
   `plant_workspace.py`, devolvendo um template SEM `{% extends %}`
   (bruto).
2. Marca `"enabled": True` na entrada correspondente de `_TABS`
   (`plant_workspace.py`) e adiciona a URL no dicionário `tabUrls` do
   JS de `shell.html`.
3. Se a tela de origem já existe como página cheia, decida entre
   **extrair** (partial reaproveitado pelos dois lados) ou
   **reescrever enxuto** — depende do quanto o workspace quer do
   MESMO conteúdo da tela cheia. **Achado na aba Sessões**: "Passos da
   Sessão" virou template novo (visão deliberadamente mais enxuta que
   o CRUD completo). **Achado na aba Receita Mash**: o editor de
   timeline (`recipe_timeline/view.html`) já era exatamente o que o
   workspace queria — extração compensou, mesmo padrão exato do
   Dashboard (`_content.html`/`_scripts.html`/`_fragment.html` +
   `_build_*_view_context(is_fragment=True)` reutilizável).
4. Se a tela nova tiver `setInterval`/listener global, seguir a
   convenção do item 2 das armadilhas acima (`window.__tabCleanup`).
5. **Terceira armadilha, achada na aba Sessões, generalizada na aba
   Receita Mash**: se a aba tem sub-navegação PRÓPRIA (trocar de
   sessão/receita sem sair da aba, sem passar pela troca de aba
   top-level da casca), o problema do `<script>` que não executa
   sozinho via `innerHTML` se repete. A casca expõe dois helpers
   genéricos, pensados pra qualquer aba futura:
   - `window.__workspaceLoadUrl(url)` — navega o conteúdo da aba atual
     pra outra URL (ex.: escolher outra sessão/receita), sem sair do
     workspace nem duplicar a lógica de fetch+executeScripts.
   - `window.__workspaceReloadCurrent()` — recarrega a MESMA URL já
     carregada, sem precisar saber qual é. Serve pra JS
     **compartilhado** entre a tela cheia e o fragmento (ex.: um
     formulário que hoje faz `window.location.reload()` direto) — o
     padrão é embrulhar num `reloadView()` que chama
     `window.__workspaceReloadCurrent()` se existir, senão cai pro
     `window.location.reload()` de sempre. Ver
     `recipe_timeline/_scripts.html` pro exemplo real (3 pontos
     trocados: adicionar etapa, resync lúpulo, remover etapa).
6. **Ação que cria/edita um registro "grande" (não é só refresh de
   dado)**: considerar `target="_blank"` no formulário/link em vez de
   navegar a página inteira ou tentar embrulhar em AJAX — visto na aba
   Receita Mash pro formulário "Gerar Sessão" (`is_fragment` controla
   isso no template). Preserva o contexto do workspace sem esforço de
   engenharia extra pra uma ação que já é, por natureza, uma saída
   do fluxo corrente.
## Saneamento local de ingredientes (incremento 1A)

`services/ingredient_sanitation_service.py` é extensão manual para o
formulário da aba Receita. `sanear_ingrediente(recipe_id, ingredient_id,
status_resolucao=..., material_id=..., commit=True)` modifica somente
vínculo/status local, valida material pelo lookup público e rejeita receita
referenciada por sessão, inclusive na lixeira. Receitas são globais; validar
o ingrediente pela receita, sem criar relação de propriedade com planta.

Esse caminho não chama `confirmar_mapeamento()` (propagação global/commit
próprio) nem `confirmar_consumo_ingredientes()` (baixa de insumos). Quantidade,
unidade, cache compartilhado e custo registrado não mudam. `commit=False`
permite composição; falha faz rollback da transação. O serviço não aplica
RBAC: controllers devem verificar autenticação, permissão de edição
de ingrediente e contexto antes da chamada.

O incremento 1B adiciona `sanitize_recipe_ingredient` em `plant_workspace.py`,
exigindo login e `recipe_ingredients.update`, e o partial manual
`_ingredient_sanitation.html`. Reutiliza o serviço local, o combo `materials`,
modal do Core e helpers AJAX. A seleção `recipe_id` é preservada no retorno
e na abertura inicial da casca. Não há proteção nova no CRUD/importador.

O incremento 1C adiciona `revise_recipe` (login, `mash_recipes.create` e
`recipe_steps.list`) e `edit_recipe_ingredient_data` (`recipe_ingredients.update`).
`criar_nova_versao()` copia volume/ingredientes/timeline/água/fermentação ativos,
remapeia pai e ingrediente dos alertas e registra `source_recipe_id` no snapshot.
A próxima versão usa o máximo do mesmo nome, incluindo a lixeira. Conflito
na constraint existente é reportado como 409, com rollback; sem migration.

`editar_dados_ingrediente()` permite somente os campos de planejamento,
valida números finitos não negativos e unidades pelo lookup público
`unidade_catalogo_lookup.get_unidade`. Código canônico é armazenado, sem
conversão automática; valores legados não alterados podem ser preservados.
Usa `sync_hop_alerts(commit=False)` e `build_recipe_snapshot()` antes do único
commit. Falha desfaz ingrediente, alertas e histórico juntos. Ambos os
serviços aceitam `commit=False` para composição transacional. Não chamar
consumo, não trocar receita de lote e não recalcular custo congelado.

`_build_recipe_view_context()` deixa de sincronizar alertas automaticamente
quando existe qualquer sessão referenciando a receita, inclusive na lixeira.
A proteção não substitui as ações explícitas avançadas do runtime/timeline.
`_ingredient_data.html` usa combo `unidades_catalogo` com `value-field=codigo`
e enums via `form-select`; edição local bloqueada em receitas com sessões.
A resposta da revisão inclui `recipe_id` novo e o helper AJAX abre essa seleção.

Detalhes, comandos e roteiro: [patch 1C](../../../../../../docs/patches/workspace-revisao-receita-ingredientes.md).

Detalhes e testes: [patch 1A](../../../../../../docs/patches/workspace-saneamento-ingredientes-servico.md).

## Preparação do envase em Sessões (2A.1)

A rota manual `prepare_session_envase` confere planta/sessão não apagadas,
pertencimento e permissões de listar lotes/envases e criar envase. Consome
o serviço manual de preparação da feature Envase; acessos ao estoque ficam
em lookups públicos. O resultado não gera envase/movimentação nem altera
o lote. Os partials `_envase_preparation.html` e `_envase_preview.html`
integram entrada/consulta no card existente. Campos do lote ou de outras
sessões enviados em query não são usados como destino. Sem migration.

[Rotas, testes e pendências](../../../../../../docs/patches/workspace-preparacao-envase.md).

## Seletores manuais e layout do workspace

As referências dos partials manuais usam `_reference_combo.html` e o componente
Core `TesseractWeakRef`. `data-weakref-ids` limita a pesquisa aos IDs fornecidos
pelo contexto; vazio significa conjunto vazio. A API aplica esse limite antes
da paginação, sem substituir validações de permissão/pertencimento no POST.
Funções usam `data-weakref-value-field="name"`. O Core emite `change` ao escolher
ou limpar uma referência e descarta respostas fora de ordem.

O conteúdo de Sessões após o resumo fica em `#pwSessionDetails`, fora das
colunas da lista e do resumo. Não recolocar os detalhes na coluna direita.
Inventário, comandos e roteiro: `docs/patches/brewstation-seletores-layout.md`
na raiz do repositório. Não há migration nesta correção.

## Testes de referências carregadas pela API

Não exigir que o HTML inicial contenha os nomes de todas as opções. Conferir
o escopo de IDs do combo renderizado, consultar a API e validar seleção real.
Consultas manuais por PK usam db.session.get; manter validações de apagamento,
permissão e pertencimento existentes. Detalhes na raiz em
`docs/patches/brewstation-testes-combos-sqlalchemy.md`.


## Workspace 2B — detalhes e estorno de envase

`tab_sessions` aceita `envase_id` junto de `session_id`, valida exclusão e
pertencimento ao lote e exige `envases.detail`/`envases.list` para o detalhe.
Links internos usam `__workspaceLoadUrl`; a casca conserva esses parâmetros
na abertura direta. A seleção explícita inválida não escolhe outro envase.
O partial `_envase_detail.html` usa os snapshots persistidos, sem simular
custos ou consultar composição atual para reconstruir consumos.

POST `/<plant_id>/sessions/<session_id>/envases/<envase_id>/reverse` exige
`brew_sessions.list`, `envases.list`, `envases.detail` e `envases.update`.
Valida todos os vínculos antes de chamar `estornar_envase`. Esse serviço
manual conserva a reserva condicional do status e as movimentações centrais
com `commit=False`, acrescentando `BrewSessionLog` antes do commit único.
A falha no log também desfaz devoluções/status. O retorno AJAX mantém o lote
e o envase selecionados; callbacks ficam no fragmento removido ao trocar aba.
Não altera tabelas, timers, etapas ou a limpeza `__tabCleanup` do Dashboard.

## Configuração local de dashboards 3A.1

POST `/brewstation/plant-workspace/<plant_id>/dashboard-layouts/<layout_id>/appearance`
é manual e autenticado, exige `dashboard_layouts.update`. Aceita apenas
`background_color`, `background_image_url` e checkbox `is_default`; os
demais campos recebidos não são aplicados. `dashboard_workspace_actions`
confere painel/planta não apagados, valida formato e salva na mesma
transação que limpa padrões de outros layouts ativos da mesma planta.
Falha faz rollback. Outras plantas, layouts sem planta e lixeira preservados.
A ação não redefine regras do CRUD avançado: duplicatas legadas são
consolidadas quando explicitamente escolhido novo padrão no workspace.

`render_background` valida também dados legados antes de renderizar, sem
reescrevê-los. Cores inválidas usam #0f1117; URLs inválidas não geram imagem.
URL aceita HTTP/HTTPS sem credenciais, ou caminho local absoluto; rejeita
protocol-relative, data/javascript, espaços e caracteres de controle.
Imagem decorativa usa src escapado, object-fit cover, z-index 0 e
pointer-events none. Canvas/widgets/tubulação mantêm seus IDs e camadas.

Contexto compartilhado no dashboard_runtime fornece cor/URL seguros para
fragmento e view. Helpers AJAX existentes carregam o painel retornado por
`layout_id`, executando `__tabCleanup` normalmente. Casca aceita layout_id
para retorno não AJAX; fragmento valida pertencimento e seleção inválida.
Não há migrations nem edição de artefatos gerados. Standby existe apenas
como campos persistidos no código conferido; runtime permanece pendente.

## Manutenção de layouts 3B

Rotas manuais POST em `/plant-workspace/<plant_id>/dashboard-layouts/<layout_id>/trash`
e `/restore`, autenticadas, exigem `dashboard_layouts.trash` e
`dashboard_layouts.restore` respectivamente, conforme CRUD atual. Usam
`maintain_layout` do serviço manual: painel pertence à planta não apagada,
estado precisa corresponder à ação. Repete estado inválido com 400, sem
novo timestamp; fora de escopo retorna 404. Payload não altera campos.

A função chama trash/restore do serviço gerado existente, sem edições no
CrudGen. Envolve gravação em try/rollback. Restauração ajusta is_default
apenas se antigo padrão conflita com outro ativo da planta, na mesma
transação do restore. UPDATE condicional antecede a restauração e reserva
a escrita no SQLite antes de conferir novamente o estado; a seleção de
padrão ativo ocorre no próprio UPDATE. Não toca widgets, planta, sessão,
estoque ou MQTT.
Remoção retorna padrão ativo ou primeiro painel restante; sem nenhum,
retorna layout_id null. Restauração retorna o painel restaurado.

JSON retorna dashboard_reload=true; casca abre Dashboard com layout_id
quando presente, ou sem seleção quando último removido. Fluxo normal usa
redirect equivalente. Carregamento continua executando __tabCleanup.
Fragmento recebe contexto da lixeira paginado/clampado em 20, trash_page
>=1 e <= total de páginas. Paginação preserva seleção explícita. O estado
vazio inclui o mesmo partial de manutenção. Modais usam chaves i18n do
Core, envio bloqueado enquanto confirma/salva, e conferem form.isConnected.
Formulários locais usam data-layout-confirm-key e chamam o helper diretamente:
não usar data-confirm-key, pois o listener global em captura confirmaria e
enviaria POST nativo além do fluxo AJAX. Teste Node inclui essa delegação real.
Após aplicar, reiniciar app/recarregar workspace para catálogo i18n em cache.
Sem migration ou delete_permanent no workspace; CRUD avançado preservado.


### Automação 4B.1 — consulta contextual

Extensão manual em `controller/plant_workspace.py` e
`templates/plant_workspace/_tab_automation.html`; sem alteração do CrudGen.
GET `/<plant_id>/tab/automation`: `q`, `rule_id`, `active` (vazio/active/inactive),
`scope` (vazio/global/session), `outcome` (vazio/success/error), `rules_page`,
`logs_page`. Enum desconhecido: 400; seleção explícita sem regra disponível:
404. Sessões apagadas e regras apagadas/externas são excluídas. Busca contém
literal com escape de curingas. Ordenação de logs por horário e ID decrescentes.
Páginas limitadas a 20 e normalizadas para o intervalo disponível.

Combo padrão `automation_rules`, IDs das regras permitidas da planta e globais.
`automation_rules.list` protege a aba; `automation_rule_logs.list` protege
consulta/conteúdo do histórico. Atalhos usam create/detail, respectivamente.
Eventos locais do fragmento usam `__workspaceLoadUrl`; sem timers/listeners
globais novos, preservando a limpeza do Dashboard feita pela casca.

O filtro contextual não modifica `automation_engine.py`: seu despacho por
sensor considera atividade/exclusão, não `session_id`. Não confundir vínculo
com isolamento de execução. Logs têm `rule_id`, não planta/sessão de origem.
Revisar essa semântica antes de integrar ativação/edição. Sem migration.


### Guarda de execução 4B.2a

`automation_engine._evaluate_rule` verifica `_session_allows_execution` antes
de cooldown/condição/resolução do ator. Globais (`session_id is None`) seguem
sem essa restrição; vinculadas exigem sessão ativa/não apagada com planta
existente/não apagada. Referências ausentes são recusadas. Leitura via
`db.session.get`, somente modelos do próprio addon; dispositivos continuam
pelo serviço público. Nenhuma migration ou alteração de controllers gerados.

Bloqueio não chama `_trigger_rule`: sem log de disparo/contador/horário novo,
sem alteração de status, estoque ou temporização. Retomar não zera cooldown.
A condição de sessão não prova pertencimento físico das funções ao equipamento:
mapeamento por planta e proveniência dos eventos ainda precisam de revisão.
Atualiza a observação de 4B.1 acima sobre ausência de guarda por sessão.


### Automação — isolamento por configuração (4B.2b)

Regras vinculadas exigem que sensor e atuador estejam mapeados somente na
planta da sessão, por mapeamentos/tanques/plantas não apagados. Cada função
precisa resolver exatamente um ator não apagado, com função disponível.
Ausência, compartilhamento entre plantas ou múltiplos atores bloqueiam novos
disparos sem gravar contador/horário/log de disparo. Regras globais preservam
o comportamento anterior e continuam compartilhadas.

Antes de operar, confira os mapeamentos na aba Planta. Configurações antigas
sem mapeamentos exclusivos deixam de disparar regras vinculadas. Isso não
altera dados nem desliga atuadores. O isolamento é pela configuração: o evento
continua contendo nome/valor, sem identificar planta física ou autenticar origem.
Logs também não passam a armazenar origem. Não há migration.


### Consolidação combinada 4B.3 / 4B.4 / 4C

`workspace_automation_service.py` é manual e valida uma whitelist de configuração.
Não aceita alterações de contador, horário, atividade ou lixeira no formulário.
Funções resolvidas pelo serviço público do DeviceManager (categoria compatível).
Sessão deve pertencer à planta; sessão vazia significa global. Criar/restaurar
mantém inativa; editar exige inativa. Manutenção por permissões próprias,
soft delete/idempotência de ações e rollback em falhas. Sem excluir logs.

`plant_workspace.py` delega controles ao controller manual `dashboard_runtime`
após RBAC e pertencimento; não recria lógica de timer/etapas. Os novos endpoints
pedem `expected_status`; avançar/voltar pedem também `expected_step_id`, conferido
com etapa ativa ou primeira operacional pendente. Conflito retorna 409. Isso
protege reenvio sequencial desatualizado, não é trava distribuída entre processos.
Avançar/voltar só active; pausa/conclusão active/paused; resync draft/active/paused.
Ajuste de etapa aberta usa `recipe_timeline_service.adjust_session_step`,
com ID do usuário e log na mesma transação, sem editar receita/status/timers.

Partials novos são manuais; referências usam weakref-combo, enums form-select.
Modais por chaves i18n via `__tesseractConfirm`, listeners locais delegados, AJAX/mensagens pelo `__workspaceSubmitForm`.
`automation_reload` na casca abre a regra salva/restaurada ou limpa a seleção
após lixo, evitando recarregar seleção apagada. Lixeira tem paginação própria.
Nada muda no catálogo de menus ou no schema. Rotas legadas seguem acessíveis.


## Revisão de navegação — etapa 5

Inventário em `docs/patches/workspace-revisao-menus.md`. A lista de ocultação
em `core/cli.py` mantém sete códigos: manutenção adicional ainda requer CRUD.
O catálogo manual `feature.py` acrescenta TX_AUTOMATION_FLOW, apontando para
landing com tab=automation e brew_plants.list; aba exige automation_rules.list.
Sync preserva is_active existente; metadados de regras/layouts/histórico são
atualizados no boot. Sem migration ou alteração de controllers gerados.
Testar comando, idempotência e preservação de estados com
`python -m pytest tests/test_hide_legacy_mash_control_menu.py -q`.


Correção de apresentação dos menus: nomes curtos preservados; description
exibida como tooltip Bootstrap no menu lateral. Sem migration. Roteiro em
`docs/patches/workspace-menu-hints.md`.
