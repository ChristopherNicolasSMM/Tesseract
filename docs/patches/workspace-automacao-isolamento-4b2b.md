# Automação — isolamento de configuração 4B.2b

05/10/2026. Implementado; validação local pendente. Depende do patch 4B.2a.
Sem migration ou `db upgrade`.

## Mudança

Além da sessão ativa/planta disponível, regras vinculadas exigem que sensor
E atuador tenham mapeamentos não apagados em tanques/plantas não apagados,
exclusivamente na planta da sessão. Duplicações dentro da mesma planta não
criam ambiguidade de planta. Compartilhamento com outra planta disponível
bloqueia. Mapeamento ausente ou apagado não é considerado disponível.

Um novo resolvedor público manual do DeviceManager devolve external_id apenas
quando há exatamente um ator não apagado para uma função não apagada. Nenhum
ORM atravessa addons. O motor usa esse resolvedor na guarda e na escolha do
alvo vinculado, evitando escolher o primeiro ator. Globais mantêm o resolvedor
e comportamento anteriores. Nenhum arquivo gerado foi alterado.

Bloqueio ocorre antes de avaliar/disparar a ação: não gera log de disparo,
contador ou horário novo e não altera sessão/timers/estoque. Não desliga atores.
Regras antigas vinculadas sem configuração exclusiva ficam bloqueadas até
regularização dos mapeamentos. Cooldown e histórico existentes são preservados.

Esta é uma guarda por configuração; o evento ainda contém só nome/valor,
sem planta física/identidade de origem. Não adiciona autenticação de evento,
vínculos físicos, snapshot de origem no log nem transação distribuída com
hardware. Regras globais continuam compartilhadas. Criação/edição/ativação
no workspace, standby e menus permanecem pendentes.

## Testes

Sintaxe Python, diff e aplicação do patch verificados. Pytest indisponível
neste ambiente; não executado com sucesso. Validação visual não realizada.

```powershell
git -c gc.auto=0 am --keep-cr .\brewstation-automacao-isolamento-4b2b.patch
python -m pytest tests/test_phase9f_automation_engine.py -q
python -m pytest tests/test_plant_workspace.py tests/test_dashboard_runtime.py tests/test_phase9f_automation_engine.py -q
```

Testes novos cobrem funções sem mapeamento, compartilhamento de sensor/ator,
mapeamentos/tanques/funções apagados, atores duplicados, resolvedor único e
retomada de sessão com configuração válida. Testes globais existentes mantidos.

## Rotas e roteiro

Não há rota nova. `/brewstation/plant-workspace/<ID_PLANTA>`:

1. Em Planta, confira os mapeamentos de sensor/atuador usados pela regra.
2. Em Automação, confira a nova mensagem e navegação/filtros.
3. Com dispositivos emulados e sessão ativa, mapeamentos exclusivos e um ator
   por função, envie leitura compatível: regra vinculada deve disparar.
4. Mapeie uma das funções em outra planta: novas leituras não devem disparar
   essa regra; contador/horário/histórico permanecem. Remova o compartilhamento
   no ambiente de teste: próximas leituras voltam a ser avaliadas, com cooldown.
5. Confira ausência de mapeamento e função com dois atores: ambos bloqueiam.
   Regra global continua seguindo o comportamento anterior.
6. Confira pausa/retomada (4B.2a) e legibilidade do aviso nos temas existentes.

Fragmento de consulta:
`/brewstation/plant-workspace/<ID_PLANTA>/tab/automation`.
