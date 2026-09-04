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
Simula leituras sem hardware real — útil pra testar antes de comprar
o equipamento.

## Comunicação em tempo real (MQTT)
Quando configurado (ver `02-primeiros-passos.md`), os dispositivos se
comunicam de fato com o sistema pela rede — leituras de sensor chegam
automaticamente, e comandos enviados (manuais ou por regras de
automação) chegam ao equipamento.

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
