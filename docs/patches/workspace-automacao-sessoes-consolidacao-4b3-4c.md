# Patch combinado — Automação e sessões (4B.3 / 4B.4 / 4C)

05/10/2026. Frentes reunidas por solicitação do usuário para reduzir a quantidade
de patches e rodadas locais. Aplicar após 4B.2a e 4B.2b. Sem migration;
**não precisa de `db upgrade`**. Validação do usuário ainda pendente.

## Automação

- Criar/editar configuração dentro da aba: nome, descrição, sessão opcional,
  sensor, atuador, condição, ação, valores, unidade, métrica e cooldown.
- Funções e sessão usam weakref-combo; funções têm value_field=name.
  Enums usam form-select. Sessão deve pertencer à planta e não estar apagada;
  vazio significa global, com aviso de alcance compartilhado.
- Funções exigem categoria compatível (sensor/atuador ou hybrid).
  Valores numéricos finitos, limites de texto, condição/ação válidas e cooldown
  inteiro não negativo. SET_VALUE exige valor. Métrica continua informativa.
- Criar salva inativa. Editar exige desativar antes; formulário não aceita
  atividade, contador, último disparo, exclusão ou campos adicionais.
- Ativar/desativar usa update. Ativar valida funções/condição/ação e, para
  vinculadas, guarda de mapeamento exclusivo/ator único do 4B.2b. Execução ainda
  exige sessão ativa/planta disponível (4B.2a). Não aciona ao clicar Ativar.
- Trash é soft delete e desativação, preserva logs/contador/último disparo;
  repetir mantém o primeiro horário de exclusão. Lixeira paginada com 20 itens
  e escopo da planta + globais. Restore mantém inativa e preserva histórico.
- As mutações têm rollback em falhas; confirmações pelo modal Bootstrap do Core,
  mensagens/AJAX pelos helpers existentes. Regras globais mantêm a resolução legada.

## Sessões e etapas

Controles contextualizados delegam às operações existentes de dashboard_runtime,
com validação extra de planta/sessão e permissões. Não há segundo motor/timer.

| Operação | Permissão | Estados aceitos no novo endpoint |
| --- | --- | --- |
| Concluir e avançar / voltar etapa | dashboard_layouts.update | active |
| Pausar/retomar / concluir sessão | brew_sessions.update | active, paused |
| Ressincronizar etapas | dashboard_layouts.update | draft, active, paused |
| Ajustar nome/alvo/permanência | brew_session_steps.update | Sessão aberta; etapa pending/active |

Controles enviam expected_status; avançar/voltar também expected_step_id.
Uma tela desatualizada recebe 409; reenvio sequencial não avança outra etapa
nem alterna pausa novamente. Não é uma trava distribuída entre processos.
Botões ficam bloqueados durante confirmação/envio. Contexto da sessão antiga
é preservado na recarga. Consultar continua sem mutação.

Voltar reinicia a etapa anterior, conforme runtime. Concluir marca completed;
não modifica a implementação existente de horário de conclusão e não desliga
atuadores. Resync preserva etapas completas e atualiza pendentes pelo serviço.
Ajuste usa adjust_session_step, registrando campo/antes/depois/operador em log
na mesma transação. Repetir o mesmo valor não duplica log. Não altera receita,
rampa, status, confirmação de ingredientes ou custo congelado do lote.

## Rotas novas

Prefixo: `/brewstation/plant-workspace/<ID_PLANTA>`.

| Método | Sufixo | Uso |
| --- | --- | --- |
| POST | /automation-rules | Criar inativa |
| POST | /automation-rules/<ID_REGRA>/edit | Editar inativa |
| POST | /automation-rules/<ID_REGRA>/activate | Ativar |
| POST | /automation-rules/<ID_REGRA>/deactivate | Desativar |
| POST | /automation-rules/<ID_REGRA>/trash | Lixeira |
| POST | /automation-rules/<ID_REGRA>/restore | Restaurar inativa |
| POST | /sessions/<ID_SESSAO>/runtime/<ACAO> | advance-step, go-back-step, toggle-pause, stop, resync-steps |
| POST | /sessions/<ID_SESSAO>/steps/<ID_ETAPA>/adjust | field=name/target_temp/duration_seconds, value |

Novo serviço manual, partials manuais e controller manual; nenhum arquivo gerado
foi alterado. Sem rotas de exclusão permanente ou catálogo de menus modificado.

## Aplicação e uma rodada de testes

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-automacao-sessoes-consolidacao-4b3-4c.patch
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_phase9f_automation_engine.py -q
```

Não precisa repetir testes de migrations/estoque exclusivamente por este patch.
O teste JavaScript é rápido e não abre o banco:

```powershell
node tests/js/test_workspace_operations.cjs
```

Ele verifica confirmação/cancelamento, bloqueio de reenvio, fragmento removido
e recuperação dos botões quando o modal está indisponível.
Resultados executados: rodada focada inicial, **38 aprovados**; regressão
conjunta, **407 aprovados em 813,69 s**; após os ajustes finais de confirmação
por i18n e guardas de ressincronização, seleção focada, **6 aprovados**.
Teste JavaScript aprovado. Diff e aplicação via git am em checkout separado
verificados antes da entrega. Ambiente auxiliar: Python 3.12, Flask 3.1.3, SQLAlchemy 2.1.3;
a validação local mantém as dependências do projeto do usuário. Sintaxe Python/Jinja/JavaScript e renderização isolada do fragmento
foram verificadas. Testes usam bancos descartáveis de testing; não banco do
repositório. Validação visual ainda deve ser feita no ambiente do usuário.

## Roteiro visual

URL principal: `/brewstation/plant-workspace/<ID_PLANTA>`.

1. **Automação:** expanda Criar regra. Busque sensor/atuador e sessão pelos
   combos. Crie uma regra inativa; veja-a selecionada sem sair da aba.
2. Edite nome/condição/ação; confira enums, limites e SET_VALUE sem valor.
   Em regra ativa, formulário pede desativar antes de editar.
3. Com dispositivos emulados, ative regra vinculada com mapeamentos exclusivos
   e ator único por função. Sem configuração válida, ativação deve ser recusada.
4. Desative, mova para lixeira, navegue suas páginas e restaure: permanece
   inativa, com histórico antigo preservado. Confira aviso para regras globais.
5. **Sessões:** escolha um lote antigo ainda aberto. Pause/retome; avance e
   volte etapa. Atualize outra aba e tente enviar estado antigo: erro 409.
6. Com receita vinculada, ressincronize e confira completas preservadas e
   pendentes atualizadas. Conclua a sessão no dispositivo emulado; controles
   de execução deixam de aparecer conforme status.
7. Expanda etapa pendente/ativa e ajuste nome, alvo ou permanência. Confira
   log com operador e valor anterior/novo; receita permanece preservada.
8. Confira usuários sem create/update/trash/restore/step.update, temas
   claro/escuro, combos AJAX e troca Dashboard → Sessões → Automação → Dashboard.
   Confirmar/cancelar deve funcionar sem duplicar listeners/timers.

## Pendências preservadas

Exclusão permanente e acessos avançados continuam no CRUD. O histórico identifica o vínculo atual da regra, sem snapshot do vínculo na
origem do disparo. O evento dos sensores continua sem origem física identificada; não afirmar isolamento
físico autenticado. Standby 3A.2, PID contínuo, eventual manutenção adicional
de sessões/etapas e matriz final de menus continuam pendentes. Este incremento
cobre as operações listadas, não encerra toda manutenção avançada da etapa 4.
