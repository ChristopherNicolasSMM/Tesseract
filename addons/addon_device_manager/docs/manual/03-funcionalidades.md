# 03 — Funcionalidades (Dispositivos)

## Funções
Tipos de leitura/ação que um dispositivo pode ter (sensor de
temperatura, atuador de aquecimento, etc.). Você pode definir uma
faixa de valores aceitável (ex.: 0 a 100) — valores fora dela são
recusados quando alguém tenta acionar o equipamento.

## Dispositivos
Cadastro dos equipamentos físicos — nome, tipo (sensor/atuador/
gateway) e protocolo de comunicação. Pode ser marcado como inativo
sem apagar (ver "Ações em massa" abaixo).

## Atores
Liga uma porta física do dispositivo a uma Função, marcando se essa
porta é um **sensor** (só leitura) ou um **atuador** (recebe comando).
Se marcar este ator como "atuador de risco" (ex.: uma resistência de
aquecimento), você define um valor seguro — se o sistema ficar fora do
ar, esse valor é aplicado automaticamente, sem depender do sistema
estar funcionando.

**Campo "Config Json" (avançado, opcional)**: só é necessário se você
ligou a Comunicação MQTT (ver `02-primeiros-passos.md`) e quer um
tópico específico em vez do padrão gerado automaticamente. Formato:

```json
{
  "mqtt_config": {
    "state_topic": "sensors/mash_tun_temp/state",
    "command_topic": "actuators/mash_heater/set",
    "qos": 1,
    "retain": false
  }
}
```

`state_topic` é de onde o sistema lê o valor (sensor); `command_topic`
é pra onde o sistema publica um comando (atuador) — preencha só o que
fizer sentido pro tipo do ator. Sem esse campo preenchido, o sistema
ainda funciona, só usa um tópico gerado a partir de um identificador
interno, menos legível de acompanhar direto no broker.

## Dispositivos Emulados

O cadastro permite selecionar um modo (`sine_wave`, `random_walk` ou
`manual`) e manter a configuração JSON associada. Nesta versão, esse
cadastro ainda **não inicia um gerador de leituras** nem publica dados
no MQTT. O estado “Em execução” e o horário da última publicação são
mantidos como campos de sistema e não podem ser alterados manualmente.
Para testar leituras, use um Bridge/hardware em modo simulado. Evite
publicar mensagens de teste em `state_topic` de produção: elas são
processadas como telemetria real e podem disparar regras de automação.

## Comunicação em tempo real (MQTT)
O protocolo operacional desta versão é MQTT (ver
`02-primeiros-passos.md`). Com o broker configurado, as leituras de
sensor chegam automaticamente, e comandos enviados (manuais ou por
regras de automação) chegam ao equipamento.

O menu **Dispositivos IoT → Testes de Comunicação** reúne os fluxos de
diagnóstico:

- **MQTT:** testa conexão, subscribe, publish e retorno no broker em um
  tópico aleatório de diagnóstico. O painel também acompanha quando um
  ator recebe telemetria em seu `state_topic`. Pela visão geral, abra o
  ator, dispositivo ou função, ou selecione o ator para ir ao fluxo MQTT.
- **Comando MQTT:** envia um valor JSON ao `command_topic` de um atuador
  ativo, respeitando tipo e limites cadastrados. Exige confirmação e não
  permite envio direto por esse fluxo em atuadores de risco ou controles
  Bridge. O seletor mostra os atuadores configurados e indica quais usam
  o fluxo protegido do Mash Control.
- **Publicação MQTT dinâmica:** permite selecionar qualquer ator para
  sugerir um tópico ou deixar o ator vazio e informar tópico e payload
  manualmente. Aceita JSON ou texto, QoS e retain. O prefixo MQTT do
  Tesseract é aplicado ao tópico. Exige confirmação porque é uma publicação
  de baixo nível: não valida limites da função nem políticas Bridge e pode
  alterar telemetria ou acionar equipamento real. Use em bancada ou com
  confirmação do efeito esperado.
  A publicação confirma o broker, não a execução física; verifique a
  telemetria/ACK publicado pelo dispositivo.
- **REST:** envia GET, POST, PUT, PATCH ou DELETE com cabeçalhos e corpo
  JSON, mostrando código HTTP, tempo, cabeçalhos e resposta. A chamada
  parte do servidor Tesseract e, por segurança, só aceita `localhost` e
  IPs numéricos privados/locais, sem seguir redirecionamentos. A chamada
  é transitória; cabeçalhos e credenciais não são salvos.
- **Mash Control:** lista os atores configurados no gateway MQTT mesmo
  antes da primeira mensagem. Enquanto a telemetria Bridge não chegar,
  as ações ficam sem confirmação e não podem ser enviadas. Com telemetria
  recente, as ações usam o contrato e as verificações de segurança do
  Mash Control e mostram o último ACK.

### Teste local do Device Bridge simulado

O arquivo `tools/mqtt_test_broker.py` pode subir o broker e também um
simulador do contrato Device Bridge v1, sem hardware. Configure o ator com
`protocol=mqtt`, `command_topic` e `state_topic`. O `device_id` do simulador
deve ser exatamente o nome técnico da função (`DeviceFunction.name`) ligada
ao ator. Os tópicos são relativos ao prefixo MQTT configurado no Tesseract.

1. No `.env`, habilite MQTT, use host `127.0.0.1`, porta `1883` e o mesmo
   `MQTT_TOPIC_PREFIX` que será usado no simulador. Para este broker local,
   deixe usuário e senha em branco.
2. Em um terminal, inicie `python tools/mqtt_test_broker.py --topic-prefix tesseract`.
   Abra `http://127.0.0.1:5055`.
3. Em outro terminal, inicie o Tesseract. Na aba **Mash Control** do painel,
   os atores aparecem; antes da telemetria Bridge v1, ficam desabilitados com
   indicação do que falta.
4. No painel Flask do broker, preencha o device_id, `command_topic`,
   `state_topic`, tipo `power` ou `pump` e política `manual_override`; inicie
   o simulador. Os tópicos precisam coincidir com o `mqtt_config` do ator.
5. Aguarde alguns segundos. O simulador publica telemetria a cada segundo;
   quando o Tesseract receber um contrato válido e recente, o seletor Mash
   Control habilita o ator.
6. Para potência, envie **Preparar potência** (ex.: 40%) e depois **Ligar**.
   Confira o comando recebido no painel do broker e o `last_command` com
   `status=applied` no estado do ator. Teste também **Liberar potência** e
   **Desligar**. Para bomba, teste `pump_set` com `true` e `false`; para
   `pump_confirm`/`pump_decline`, marque a opção de confirmação pendente antes
   de iniciar o simulador.
7. Pare o simulador e aguarde mais de cinco segundos: os comandos Mash devem
   ser bloqueados por telemetria ausente/desatualizada. Use `local_only` para
   confirmar que somente `power_off` é aceito.

O simulador não energiza GPIO, resistência, bomba ou válvula. `applied` é
somente confirmação lógica da simulação.

O teste REST verifica a chamada de saída e sua resposta. O addon ainda
não fornece uma rota genérica para receber telemetria REST de devices;
essa integração precisa definir autenticação e contrato por dispositivo.

## Regras de automação
Em "Controle de Mostura", você pode criar regras do tipo "se a
temperatura cair abaixo de X, ligue o aquecedor" — elas disparam
automaticamente toda vez que uma leitura nova chega, sem precisar de
ninguém clicando em nada.

## Ações em massa

Nas listas de Dispositivos e Atores, marque várias linhas e use a
barra que aparece pra **Apagar** ou **Inativar** de uma vez. Funções e
Dispositivos Emulados só têm "Apagar" — não têm um estado de
ativo/inativo próprio.
