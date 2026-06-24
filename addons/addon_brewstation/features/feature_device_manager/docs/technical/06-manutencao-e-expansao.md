# 06 — Manutenção e Expansão (Feature Device Manager)

## Adicionar um novo tipo de função

Não precisa de migration — `DeviceFunction` é uma tabela normal,
basta cadastrar pela tela ou API.

## Integração MQTT real (ainda não implementada)

`external_id` de `DeviceMetadata`/`DeviceActor` já está pronto para
ser usado como identificador em tópicos MQTT — falta o cliente/broker
de fato, que pertence a uma fase futura (job runner/background).
