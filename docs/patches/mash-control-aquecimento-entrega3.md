# Aquecimento — entrega 3: telemetria e arbitragem

Plano registrado antes da implementação (20/10/2026).

1. Contrato versionado entre Bridge e Device Manager: demanda automática antes do
   limite, teto, duty automático limitado, duty selecionado pelo árbitro, duty da
   janela aplicada, saída lógica GPIO, proprietário do controle, origem real/simulada,
   boot, sequência e data UTC. Sem afirmar potência física/chama por um GPIO.
2. Bridge publica estados dos atuadores com state_topic; preserva sensores e
   comandos legados. Janela TPC mantém o comportamento acordado. Prioridade continua
   emergência/failsafe > manual > receita local > repouso. Política por aquecedor
   permite manter override MQTT legado ou bloquear controle externo (OFF permitido).
3. Tesseract decodifica JSON no ingresso MQTT, valida telemetria, rejeita replay,
   mensagens retidas e timestamps inválidos. Comandos não atualizam observações.
   Importador preenche tópicos MQTT ausentes sem substituir ajustes existentes.
4. Configurar mapeamento do controlador por tanque; widget mostra métricas e origem.
   Regra pode exigir demanda desse Bridge (somente receita local ativa, dados recentes
   e backend real) ou manter o sensor percentual da entrega 2. Sem novo PID no servidor.
5. Testes unitários, contrato comum nos dois repositórios, transporte MQTT simulado,
   regressões, Windows/Linux por caminhos portáveis; atualizar documentação e publicar.

Não inclui automação de GLP, solicitação automática de override externo, transferência
de água, medição elétrica ou certificação de proteções. Gás continua manual/advisory.
Não se presume sincronismo entre receita local do Bridge e sessão do Tesseract; alvo
e temperatura recebidos devem coincidir com o contexto para liberar a condição.

## Implementação

- Frame de aquecimento v1 no state_topic existente, com fixture comum nos dois
  repositórios. Publicação após aplicar o controle; estado final de failsafe enviado
  antes da desconexão em melhor esforço, sem atrasar a rotina de desligamento.
- PID expõe demanda antes do teto sem alterar o cálculo de saída/anti-windup.
  Runtime distingue seleção da janela efetiva e registra origem manual local/remota.
- Política YAML `manual_override` compatível ou `local_only` (remoto somente OFF).
  O Bridge é a autoridade; o Device Manager também bloqueia comandos incompatíveis
  com a última política recebida. Não há loop PID concorrente no servidor.
- Ingresso JSON tipado, replay/retention/clock guards, DTO público de telemetria;
  estado retido pode ser cache legada, mas não observação fresca para regras.
- Controlador por tanque e demanda `sensor|bridge`, com isolamento de planta,
  frescor e compatibilidade do contexto. Painel distingue métricas e dados antigos.
- Importador preenche tópicos faltantes sem apagar os personalizados.
- Sem migration nova: head existente `c18f7d23a904` permanece. Requer as migrações
  anteriores aplicadas. O Bridge não tem migração de banco.

## Roteiro de validação

No Bridge:

```sh
python -m pytest -q
```

No Tesseract:

```sh
python -m pytest tests/test_bridge_heating_telemetry.py tests/test_heating_requests.py tests/test_heating_configuration.py tests/test_bridge_import.py tests/test_phase9d_device_service_mqtt.py tests/test_phase9f_automation_engine.py tests/test_dashboard_runtime.py tests/test_module_discovery.py -q
node --test tests/js/*.cjs
```

Teste de contrato compara o payload produzido pelo Bridge com a fixture comum.
Também foi gerado um payload pelo publicador real e entregue ao adaptador MQTT real
no Tesseract em memória: demanda 95%, seleção 60% e janela 100% preservados. Os quatro
scripts inline do dashboard renderizado foram verificados com `node --check`.
Sem broker de rede, hardware real ou sessão de navegador/Chromium nesta validação.
Windows/Raspberry Pi e broker da instalação dependem da validação local.

## Continuidade

Telemetria não sincroniza receitas nem mede potência elétrica. A nova integração não
aciona fontes automaticamente; pedidos continuam auditados e atendidos pelo operador.
Automação física adicional, medição elétrica, supervisão de chama e sensores de gás
continuam fora desta entrega. Não há confirmação fictícia de proteções.

## Resultado

- Tesseract: **265 testes Python aprovados** (148 de contrato/regras/configuração/
  importação/MQTT/automação e 117 de dashboard/descoberta).
- Bridge: **491 testes Python aprovados** (suíte completa).
- Interface: **17 testes JavaScript aprovados**, além dos quatro scripts inline reais.
- Fixture comum idêntica e transporte do payload real entre os componentes verificados.
- Três avisos legados `Query.get()` nos testes antigos do importador; sem falhas.
- Os 27 problemas antigos de custos/envase da entrega 1 não fazem parte desta suíte
  selecionada e não foram alterados nesta entrega.
