# 03 — Funcionalidades (Dispositivos)

## Funções
Tipos de leitura/ação que um dispositivo pode ter (sensor de
temperatura, atuador de aquecimento, etc.). Você pode definir uma
faixa de valores aceitável (ex.: 0 a 100) — valores fora dela são
recusados quando alguém tenta acionar o equipamento.

## Dispositivos
Cadastro dos equipamentos físicos.

## Atores
Liga uma porta física do dispositivo a uma Função. Se marcar este
ator como "atuador de risco" (ex.: uma resistência de aquecimento),
você define um valor seguro — se o sistema ficar fora do ar, esse
valor é aplicado automaticamente, sem depender do sistema estar
funcionando.

## Dispositivos Emulados
Simula leituras sem hardware real — útil pra testar antes de comprar
o equipamento.

## Comunicação em tempo real (MQTT)
Quando configurado, os dispositivos se comunicam de fato com o
sistema pela rede — leituras de sensor chegam automaticamente, e
comandos enviados (manuais ou por regras de automação) chegam ao
equipamento.

## Regras de automação
Em "Controle de Mostura", você pode criar regras do tipo "se a
temperatura cair abaixo de X, ligue o aquecedor" — elas disparam
automaticamente toda vez que uma leitura nova chega, sem precisar de
ninguém clicando em nada.
