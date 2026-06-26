# 01 — Visão Geral (Feature Device Manager)

## Propósito

Gestão de dispositivos IoT (sensores/atuadores): funções (`DeviceFunction`),
metadados de dispositivo (`DeviceMetadata`), atores que associam porta
de device a função (`DeviceActor`), e dispositivos emulados para
testar sem hardware real (`EmulatedDevice`).

Portado de `plugin_device_manager` (BrewStation original). Descartado
`model/exemplo.py` (placeholder/lixo, não migra).

## Melhorias sobre o original

- **`relationship()` ORM habilitado** — o BrewStation original
  desabilitava de propósito porque o mecanismo de prefixo dele
  quebrava a configuração do mapper. No Tesseract isso foi testado e
  funciona (ver BACKLOG.md, Fase 5b/6).
- **PK Integer + `external_id` UUID** — skill 02, "Regra de PK
  externa". O original usava UUID como PK; aqui o `id` interno é
  Integer (consistente com toda outra tabela), e o UUID vira
  `external_id`, exposto a sistemas externos.
- **Bug corrigido**: `EmulatedDevice.functions_config` usava
  `default={}` (dict mutável compartilhado entre instâncias) —
  trocado por `default=lambda: {}`.

## Dependências

Nenhuma (`requires: []`) — é a Feature mais "de base" do Addon,
referenciada por `feature_mash_control` (FK cross-Feature, mesmo
Addon — permitido, skill 02).

## Tabelas

`tesseract_brewstation_dvm_function`, `..._device`, `..._actor`,
`..._emulated_device`.
