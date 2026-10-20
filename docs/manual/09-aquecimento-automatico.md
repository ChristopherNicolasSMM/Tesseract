# Aquecimento automático protegido — ambiente de testes

Esta entrega permite comandos reais quando o Bridge está em `backend: real`.
O padrão de instalação não é alterado: nenhuma fonte existente é convertida ou
habilitada automaticamente. O operador habilita explicitamente pelo widget.
Sem nova migração; as migrações anteriores de aquecimento devem estar aplicadas.

## Arquitetura e proteção externa

Tesseract autoriza por até 10 segundos; o Bridge toma a decisão liga/desliga usando
seu sensor local. O servidor renova a autorização a partir de telemetria válida,
mesmo sem navegador aberto. O dashboard não executa o controlador.

Pré-requisito informado para GLP: válvula normalmente fechada e proteção externa
de chama que interrompe sua alimentação e aciona sirene, independente do software.
A proteção deve impedir retorno do gás após falha até rearme manual no circuito.
A instalação e o ensaio desse conjunto são responsabilidade do profissional que o
executa. A declaração no YAML não prova sua presença nem eficácia.

Não existe entrada de retorno dessa proteção nesta entrega. Se ela cortar corrente,
o GPIO pode continuar reportando ON, mesmo com a válvula fechada. O software não
percebe a perda de chama, não confirma ignição, não aciona faísca e não pode garantir
rearme por software depois dessa falha: o bloqueio/rearme é do circuito externo.

Temporizações e comandos OFF exigem processo Bridge e GPIO funcionando. Morte abrupta,
travamento do sistema operacional, relé colado e falta de energia não são garantias
fornecidas por Python; o projeto elétrico precisa tratar o estado seguro nesses casos.
Use o corte físico para parada imediata; uma requisição web não é botão de emergência.

## Configurar o Bridge

Atualize os dois repositórios. No Bridge, use o exemplo independente
[`devices.heating-source.yml.example`](https://github.com/ChristopherNicolasSMM/Tesseract-Device-Bridge/blob/main/data/public/devices.heating-source.yml.example)
para iniciar simulação no Windows ou Linux. Exemplo de execução a partir do repositório:

```text
python run_bridge.py data/public/devices.heating-source.yml.example
```

O arquivo usa `backend: simulated`, broker `localhost`, prefixo `brewery` e painel
`127.0.0.1:5001`. Ajuste o broker à instalação; o painel do Tesseract usa outra porta.
A temperatura simulada inicia em 60 °C e pode ser alterada no painel do Bridge.
Não use `run_panel.py` isolado: ele não roda o loop MQTT/controlador.

Para uma fonte existente, acrescente `hardware.heating_source` ao atuador digital,
com `participation: primary` ou `auxiliary`, `temperature_sensor` apontando ao id do
sensor local e `external_flame_cutoff: true` somente para o conjunto protegido.
A fonte exige `is_risk: true`, `failsafe_value: false`, `state_topic` e `command_topic`.
Não declare `window_seconds`, PWM ou `external_control_policy` na solenoide.

No auxiliar, acrescente `controller_device: <id do aquecedor PID local>`. Esse
controlador mantém sua janela atual e pode continuar com
`hardware.external_control_policy: local_only`. A política restringe comandos da
resistência; não bloqueia a autorização estruturada da fonte separada.

Para hardware real, mantenha a configuração física adequada ao seu dispositivo
(sensor/driver, endereço, pino e polaridade do relé). O exemplo simulado não é
esquema de ligação elétrica nem configuração pronta de sensor real.

## Configurar Planta e widget

1. Importe/atualize os dispositivos do Bridge no Device Manager. Confirme tópicos e
   funções únicas. Use MQTT com autenticação/ACL e mantenha os relógios sincronizados.
2. Em BrewStation → Planta → Aquecimento e água de lavagem, selecione o sensor
   principal do tanque. A função precisa corresponder exatamente ao id
   `temperature_sensor` do Bridge. Para auxiliar, selecione também o controlador PID
   correspondente a `controller_device`.
3. Cadastre/edite a fonte: tipo Gás, participação igual à do YAML, função do atuador,
   modo **Automático protegido (Bridge)** e fonte disponível. Salvar não a habilita.
4. Configure os limites antes de iniciar a sessão. A configuração fica bloqueada
   durante sessões ativas/pausadas. Limites existentes não mudam sem nova habilitação.
5. Inicie uma sessão. Para processo/mostura, exige uma etapa ativa do tanque; o alvo
   vem dela. Para HLT/sparge, usa o alvo planejado no tanque. Não há medição de volume,
   controle de pressão ou transferência automática de água.
6. Adicione/use o widget Aquecimento desse tanque. Confira o backend. O botão
   **Habilitar automático (simulação/saída real)** envia uma autorização, não um ON
   incondicional. Aguarde telemetria confirmando habilitação e saída lógica.
7. **Parar automático** interrompe renovação e solicita OFF. Se a mensagem não chegar,
   o Bridge desabilita após 10 segundos da última autorização aceita, mais um ciclo
   do loop (normalmente 2 s). Não há religamento automático após expiração.

Operação exige permissão `brew_sessions.update`; configuração exige
`brew_plant_vessels.update`. Habilitações/paradas e operador são registradas no log
servidor. Não há histórico de confirmação física nem novo relatório de auditoria.

Nesta versão, execute HTTP e receptor MQTT do Tesseract no mesmo processo, sem
múltiplos workers/reloader. Autorizações ficam em memória por aplicação; reinício
as perde. Não existe coordenação distribuída entre workers.

## Regras e valores de fábrica

| Parâmetro | Padrão | Faixa configurável |
|---|---:|---:|
| Demanda mínima auxiliar | 80% | 10–100% |
| Distância abaixo do alvo para ligar | 2 °C | 1–20 °C |
| Condição sustentada para ligar | 10 s | 1–120 s |
| Tempo mínimo desligado | 30 s | 10–300 s |

O tempo mínimo desligado vale também após habilitar. Principal usa temperatura;
auxiliar usa temperatura **e** demanda PID antes do teto, com receita local, contexto
atualizado nos últimos 5 s, alvo compatível e sem override manual/failsafe.
A temperatura MQTT e a leitura do Bridge devem concordar em até 0,5 °C.

Uma vez ligado, o auxiliar desliga quando a demanda chega ao limite menos 10 pontos
percentuais. As duas participações desligam a 0,5 °C abaixo do alvo ou acima.
Exemplo: alvo 65 °C, entra em até 63 °C, corta em 64,5 °C; a inércia térmica ainda
exige ajuste e validação física. Nenhum tempo mínimo ligado adia o corte.
Não é modulação de vazão nem controle específico da intensidade de fervura.

Alvo +3 °C dispara emergência geral no Bridge. Erro de sensor ou escrita usa o
bloqueio geral existente. OFF genérico, pausa/encerramento/troca de etapa ou alvo,
telemetria vencida, falha e reinício interrompem a autorização; nova ação explícita
é necessária. Queda do servidor/rede é coberta pela expiração local enquanto o
Bridge continua executando. Comandos antigos/repetidos/retidos não podem habilitar.

## Validação antes do ensaio físico

Teste inicialmente com backend simulado: habilitação; espera; ON; aproximação do alvo;
OFF; pausa; desconexão MQTT; reinício dos dois processos; sensor inválido. Reiniciar
ou retomar sessão não deve rearmar. Depois valide em bancada a polaridade real e o
corte independente com profissional responsável. Os testes automatizados desta
entrega não certificam o circuito de gás, Windows ou Raspberry Pi.

Sensores de vazamento, retorno da proteção de chama, nível/fluxo, watchdog elétrico,
coordenação multiworker e controle de fervura por intensidade seguem no backlog.
