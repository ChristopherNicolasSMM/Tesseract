# 05 — Casos de Uso (Addon BrewStation)

Casos de uso detalhados vivem em cada Feature
(`features/*/docs/technical/05-casos-de-uso.md`). Em nível de Addon,
o único caso de uso transversal é:

## UC01 — Regra de automação cruza duas Features

- **Ator**: usuário com `automation_rules.create`
- **Fluxo**: cadastra uma `AutomationRule` (`feature_mash_control`)
  apontando para um sensor e um atuador, ambos `DeviceFunction`
  (`feature_device_manager`)
- **Limitação atual**: a regra fica registrada, mas nenhum motor a
  executa de fato (sem job runner/scheduler ainda)
