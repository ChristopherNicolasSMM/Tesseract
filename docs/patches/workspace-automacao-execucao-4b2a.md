# Automação — guarda de execução 4B.2a

05/10/2026. 4B.1 validado pelo usuário. Novo patch implementado, aguardando
validação local. Sem migration ou `db upgrade`.

## Problema e comportamento

O motor avaliava regras vinculadas mesmo com sessão pausada/concluída/apagada.
Agora a avaliação exige sessão `active`, não apagada, com planta existente e
não apagada. Sessão/planta ausente e sessão sem planta também bloqueiam.
Regras globais continuam avaliadas pelo evento de sensor, condição e cooldown.

A guarda roda antes de resolver a ação. Bloquear não escreve logs de disparo,
contador ou último horário; não altera timers, status ou estoque. Pausar não
desliga atuadores já ligados. Retomar avalia novas leituras sem reproduzir as
leituras da pausa e sem zerar cooldown. ON/OFF/TOGGLE/SET_VALUE continuam usando
os pontos públicos existentes dos dispositivos.

A identificação de função por nome continua a mesma: esta guarda não garante
isolamento físico entre plantas que compartilhem funções. Não foi acrescentada
validação de mapeamentos/proveniência do evento. Logs globais continuam sem
planta de origem. Criar/editar/ativar no workspace continua pendente, assim
como standby 3A.2 e revisão de menus.

## Arquivos e validação

Motor manual `services/automation_engine.py`, aviso da aba Automação,
manuais, documentação técnica, plano e BACKLOG. Sem arquivos gerados alterados.
Testes cobrem estados bloqueados, exclusão/referências ausentes, atuação com
sessão ativa, pausa/retomada, cooldown e comportamento global já existente.
Sintaxe Python e aplicação do patch verificadas. Pytest indisponível no Python
deste ambiente; não foi executado com sucesso. Validação visual não realizada.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-automacao-execucao-4b2a.patch
python -m pytest tests/test_phase9f_automation_engine.py -q
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_phase9f_automation_engine.py -q
```

## Rotas e teste visual

Não há rota nova. `/brewstation/plant-workspace/<ID_PLANTA>` → Automação
mostra a nova regra de execução no aviso. Fragmento:
`/brewstation/plant-workspace/<ID_PLANTA>/tab/automation`.

No ambiente de teste com dispositivo emulado:

1. Vincule uma regra de teste a sessão/planta disponíveis. Com sessão ativa,
   envie leitura que satisfaça a condição e confira um disparo no histórico.
2. Pause pelo controle existente do Dashboard. Envie nova leitura: nenhum
   novo disparo dessa regra, contador/horário preservados; ator não é desligado.
3. Retome e envie outra leitura: só dispara se o cooldown estiver liberado.
4. Confira regra global: continua funcionando independentemente da sessão.
5. Confira a mensagem nos temas claro/escuro; consultas/paginação continuam
   funcionando e não produzem disparos ou escrita em estoque.

Rotas existentes de pausa/retomada:
`POST /brewstation/dashboards/sessions/<ID_SESSAO>/toggle-pause`
(`brew_sessions.update`). O patch não modifica essa rota.
