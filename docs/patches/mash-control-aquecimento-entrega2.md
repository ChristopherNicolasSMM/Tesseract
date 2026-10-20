# Aquecimento — entrega 2: regras e solicitações

## Plano registrado antes da implementação (2026-10-20)

1. Configurar uma regra por tanque, associada a uma fonte disponível em modo
   solicitação: distância mínima do alvo, histerese, tempo mínimo, intervalo entre
   solicitações, validade e idade máxima das leituras. Demanda acima de X% opcional,
   sempre vinculada a sensor numérico percentual do próprio tanque.
2. Avaliar no servidor pelos eventos de observação recebida, mesmo sem dashboard
   aberto. Preservar a distinção entre comando e leitura: disponibilizar observação
   com origem/data no serviço público do Device Manager, sem inferir demanda do
   comando ou da potência nominal. Sem leitura real, bloquear a condição de demanda.
3. Persistir estado e solicitações auditáveis. Permitir reconhecer, recusar e concluir
   solicitações no widget. A resposta declara uma ação do operador; não comprova chama
   ou funcionamento e nunca envia comando físico. Evitar repetição por histerese,
   validade, conflito de resposta e intervalo mínimo. Revalidar antes de reconhecer.
4. Exigir uma única sessão ativa, sensor principal válido e alvo aplicável ao tanque.
   Em processo, usar etapa ativa; HLT/sparge preservam seu próprio alvo. Pausa, troca
   de etapa, dados inválidos/antigos e reinício invalidam contexto; não reaproveitar
   um pedido antigo como autorização. Registrar motivos e identidade da resposta.
5. Manter configuração na aba Planta e ações no widget existente, com permissões
   no servidor, isolamento por planta e sem novo CRUD/menu. Migração aditiva.
6. Testar motor, proveniência, continuidade temporal, isolamento, respostas concorrentes,
   interface, migração e regressões relevantes. Publicar depois da validação.

## Limites

Não inclui abertura de solenoide, atuação de resistência/bomba, novo PID, arbitragem
com o Bridge, transferência de água ou confirmação de proteções. Automação física
continua na entrega 3. Fonte a gás permanece sob operação manual do responsável.
Avaliação por eventos exige novas leituras para comprovar continuidade; não usa o
navegador como relógio. Um sweep de manutenção será registrado no agendador existente
para instalações que o habilitem; a resposta sempre verifica expiração/frescor.

## Implementação e operação

- Regra persistida por tanque, desabilitada por padrão; fonte disponível em modo
  solicitação, principal ou auxiliar. Defaults definidos no serviço e apresentados
  no formulário/manual. Demanda ausente não é inferida de comandos.
- Observações recebidas têm DTO/evento próprios no Device Manager; cache e eventos
  legados continuam compatíveis. O caminho novo não publica comandos MQTT.
- Motor usa eventos e reconciliação das ações de sessão; polling do widget não
  modifica o estado. Tarefa opcional `brewstation.evaluate_heating_requests` no
  agendador Core, com configuração no manual, reconcilia instalações sem eventos.
- Estado por tanque e auditoria `HeatingRequest`, com contexto/regra/fonte no disparo,
  declarações de usuário e horários preservados. Exclusão permanente da auditoria e
  dos pais referenciados é bloqueada também por guards ORM, inclusive em SQLite.
- Widget exibe os cinco pedidos mais recentes, motivos, declarações e ações conforme
  permissão/validade. A resposta verifica novamente o contexto e compara o status.
- Migration aditiva `c18f7d23a904` após `b04e7c98d216`; execute `python run.py db upgrade`.
  Preserva configuração/leituras anteriores; downgrade bloqueado com histórico/estado.
- [Manual](../manual/08-aquecimento-hlt-sparge.md) e
  [contrato técnico](../technical/08-aquecimento-hlt-sparge.md).

## Validação

Os módulos de regressão são dashboard, timeline, Device Manager/MQTT, motor legado
e descoberta (220 casos). O recorte do workspace cobre aba Planta, mapeamentos,
runtime e automação (37 casos; 200 deselecionados). Os testes da entrega 1 também
permanecem na validação. As 27 falhas históricas de custos/envase documentadas na
entrega 1 não foram corrigidas nem reexecutadas na íntegra nesta entrega.

```sh
python -m pytest tests/test_heating_requests.py tests/test_heating_configuration.py tests/test_dashboard_runtime.py tests/test_recipe_timeline.py tests/test_phase9d_device_service_mqtt.py tests/test_phase9f_automation_engine.py tests/test_module_discovery.py -q
python -m pytest tests/test_plant_workspace.py -k "tab_plant or mapeamento or runtime or automation or sessao_paus or toggle_pause" -q
node --test tests/js/*.cjs
```

A interface foi validada por renderização HTML, sintaxe dos quatro scripts inline
reais e testes DOM; sem Chromium disponível para sessão visual. Validação executada
em Linux/SQLite, sem broker/hardware real. Windows e Raspberry Pi dependem da validação
local do operador. Nenhum caminho de código novo depende de separadores do sistema.

Resultado: **313 testes Python aprovados** (37 novos, 19 da configuração anterior,
220 de regressão e 37 do workspace selecionado) e **16 testes JavaScript aprovados**.
Head Alembic único `c18f7d23a904`; repetição de upgrade sobre esquema ORM atual
verificada sem duplicar índice. Guards de preservação de auditoria e pais testados.
