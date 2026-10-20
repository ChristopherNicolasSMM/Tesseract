# Mash Control — contrato de aquecimento (entregas 1 e 2)

Plano e etapas: [expansão](../patches/mash-control-aquecimento-expansao.md).
Operação: [manual](../manual/08-aquecimento-hlt-sparge.md).

## Persistência e limites

`BrewPlantVessel.heating_config_json` armazena o perfil por tanque; `heating_version`
é incrementada por comparação e troca. Campos são somente leitura no CRUD genérico,
para que a escrita passe por `heating_configuration_service` e suas validações.
Não há segundo cadastro de dispositivos nem novas tabelas de atuadores.

Perfil: `usage` (`process|hlt|sparge`), `primary_sensor_mapping_id`, `target_temp`
(0–110 °C, opcional), `planned_volume_liters` (0–100000 L, opcional) e `sources`.
Fonte: UUID local, nome até 100 caracteres, `type` (`electric|gas|other`),
`role` (`primary|auxiliary`), `mode` (`manual|advisory`), `enabled`, potência nominal
opcional 0–10000 kW e `device_function_name` opcional. `advisory` permite
solicitações ao operador na entrega 2; não envia comandos. Máximo de vinte fontes e uma principal.
Limites numéricos são validações de armazenamento, não especificações de equipamento.

O sensor precisa ser mapeamento de temperatura numérico válido do mesmo tanque.
A função da fonte precisa ser atuador/híbrido já mapeado no tanque e não pode ser
repetida entre suas fontes. Referências a Device Manager usam o serviço público
`device_function_lookup` e o nome da função; não há FK/objeto ORM entre addons.
Valores não finitos e seleções inválidas são rejeitados.

A escrita serializa pela planta, rejeita sessões ativas/pausadas e exige a versão
lida pela tela. Conflitos retornam 409 com rollback. Alterações de configuração
são feitas fora da sessão; não foi introduzido snapshot de configuração da sessão.

## Rotas e widget

`POST /brewstation/plant-workspace/<plant>/vessels/<vessel>/heating/<action>`:
`profile`, `source`, `remove-source`, `rule`. Login e `brew_plant_vessels.update` obrigatórios;
planta/tanque são verificados no servidor. JSON usa `expected_version`; edição e
remoção de fonte usam `source_id`. Erros de validação retornam 400, ausência 404,
conflito 409. Exceções inesperadas desfazem a transação e registram o erro.

O widget `heating` reutiliza criação/edição/snapshot do dashboard, ligado por
`vessel_id` e limitado à planta do layout. O endpoint de acionamento rejeita esse
tipo mesmo se uma função for injetada no registro. Configurar e consultar não chama
`device_service.set_value`. As permissões existentes de dashboard continuam válidas.

Snapshot publica temperatura e origem do alvo; demanda percentual observada somente
quando válida para a regra, caso contrário `null`,
`can_actuate=false` e proteções sem confirmação. O valor do sensor é o último cache
numérico finito, sem garantia de idade. Não se usa cache de comando para afirmar
funcionamento de fonte. No tipo `process`, uma etapa ativa da sessão da mesma planta
pode substituir o alvo planejado. HLT/sparge preservam o alvo do perfil.
O widget Tanque também passa a usar a seleção principal explícita/canônica/única.

Templates escapam entradas e o renderer usa `textContent`. Combos seguem o componente
de referência existente e são restritos ao tanque. Configuração fica na aba Planta,
sem novos menus de CRUD. `heating_workspace.py` usa descoberta padrão de blueprints.

## Migração e validação

Revisão aditiva `b04e7c98d216`, anterior `a93dbe671ca5`, acrescenta JSON anulável e
versão inteira não anulável com default 0. Verifica colunas já criadas compatíveis.
Downgrade é bloqueado se houver configuração/versão utilizada, evitando perda
silenciosa. Caminhos de código não dependem de separadores do SO; os testes de
migração usam `pathlib`. Validação local usa SQLite/Linux; Windows e Raspberry Pi
precisam da validação do operador nos respectivos ambientes.

```sh
python -m pytest tests/test_heating_configuration.py tests/test_heating_requests.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_phase9d_device_service_mqtt.py tests/test_phase9f_automation_engine.py tests/test_module_discovery.py -q
node --test tests/js/*.cjs
```

Testes cobrem ausência de comandos, sensor principal, limites numéricos, fontes,
isolamento de plantas, RBAC, concorrência por versão, sessões ativas, CRUD genérico,
rotas, renderização HTML, renderer JS e preservação/bloqueio de perda na migração.

## Entrega 2 — observações e motor de solicitações

Migration `c18f7d23a904`, após `b04e7c98d216`, acrescenta `heating_runtime_json`
no tanque e `tesseract_brewstation_mashctrl_heating_request` (auditoria interna).
Downgrade verifica dados de auditoria e estado antes de remover qualquer estrutura.
Não há novo menu ou CRUD para editar auditoria; o modelo é somente leitura.
Guards de exclusão também impedem remover a auditoria e tanques/sessões que a
referenciem pelos caminhos legados de exclusão permanente, inclusive em SQLite.

O Device Manager expõe `get_observation(identifier)` como DTO primitivo:
`value`, `observed_at`, `source=mqtt_state`, `actor_external_id`. Apenas
`update_from_mqtt` escreve os campos de observação, antes de publicar
`device_manager.actor.observation_received(function_name=...)`. O cache legado
`get_value` e o evento anterior são preservados. `set_value`, mesmo com
`publish=False`, não cria nem atualiza observações. Caches antigos sem esses campos
não são promovidos a telemetria: aguarda-se nova recepção. A origem indica o caminho
de ingresso de estado, não autenticação/prova física do dispositivo.

`heating_request_service` registra um listener idempotente no EventBus e a tarefa
`brewstation.evaluate_heating_requests` no registro público de tarefas. Não há timer
no navegador, novo scheduler ou PID. A tarefa usa o agendador Core existente, opt-in;
configuração operacional está no manual. Observações e ações explícitas de pausa,
parada, avanço/retorno, ressincronização e ajuste de alvo reconciliam a planta.
Edições por caminhos legados são revalidadas na próxima observação/tarefa/resposta.

A regra fica em `heating_config_json.rule`: `enabled`, `source_id`,
`require_demand`, `demand_mapping_id`, `demand_threshold`, `demand_hysteresis`,
`minimum_gap`, `gap_hysteresis`, `minimum_seconds`, `cooldown_seconds`,
`validity_seconds`, `max_age_seconds`. Configuração usa a mesma versão/serialização
por planta da entrega 1 e é bloqueada durante sessões ativas/pausadas. Valores
não finitos, unidades inadequadas, referência de outro tanque e histerese inválida
são rejeitados. Defaults estão na constante `DEFAULTS` e no formulário/manual.

Condições: uma única sessão ativa (outra ativa/pausada bloqueia), fonte disponível
em `advisory`, sensor principal válido e observação recente, finita e na faixa.
Processo requer uma única etapa ativa deste tanque; HLT/sparge usam o alvo próprio.
Demanda opcional exige sensor percentual numérico (não atuador/híbrido) do tanque.
Entrada usa distância ≥ limite e demanda > limite. Saída usa distância ≤ limite
menos histerese ou demanda ≤ limite menos histerese. A condição de entrada deve
permanecer durante o tempo mínimo, sem intervalos de avaliação acima da idade máxima.
A faixa intermediária mantém o pedido existente; não inicia um novo temporizador.

O estado persistido armazena contexto (sessão/etapa/alvo/versão/fonte), início da
condição, última avaliação/pedido e trava até saída da faixa. O lock da planta é
adquirido antes de reler o tanque. Isso serializa avaliadores e alterações de
configuração. Uma leitura/candidato anterior à inicialização do processo não é
reutilizada como autorização; pedidos anteriores ao início do processo ficam
inaptos para resposta e são reconciliados por evento/tarefa. Use relógios UTC
sincronizados. O estado é conservador ao iniciar novos processos.

`HeatingRequest` preserva contexto/regra e valores no disparo, datas, fonte,
sessão e status `requested|acknowledged|declined|completed|cancelled`.
`context_json.responses` preserva cada declaração (ação/usuário/horário), inclusive
reconhecimento seguido de conclusão por usuários diferentes. Recusa, conclusão e
expiração não liberam imediatamente novo pedido; exige saída da faixa e cooldown.
Cancelamentos preservam declarações anteriores e explicam revisão manual da fonte.

`POST /brewstation/plant-workspace/<plant>/vessels/<vessel>/heating/requests/<id>/respond`
exige login e `brew_sessions.update`; aceita `action=acknowledge|decline|complete`.
Reavalia sob o lock, persiste cancelamentos descobertos e usa comparação de status
para rejeitar respostas concorrentes com 409. Planta/tanque/pedido são escopados no
servidor. `request_rule` no snapshot expõe os cinco pedidos mais recentes e flags
para resposta; polling não modifica estado nem dispara avaliação. Sessão histórica
não oferece ações para pedidos da sessão atual. JS cria texto/botões por DOM.

Sem novas observações/tarefa, uma linha persistida pode continuar `requested` após
expirar, mas `currently_valid=false` e sem botões; a resposta é recusada com
reconciliação. Isso não autoriza atuação. Não há abertura/corte de gás ou confirmação
de potência/chama/proteções em nenhuma transição.
