# 01 — Visão Geral (Sistema)

> Esqueleto — preencher conforme a Fase de construção avança.

## Propósito

Tesseract é o Hub modular (Core + Addons + Features + Plugins) que unifica
PyTeca (CrudGen, RBAC, versionamento), BrewStation (motor de descoberta e
registro de módulos) e DEVStationFlask (transações, motor de regras,
Designer drag-and-drop, OData) em uma única base.

## Dependências do Core

Nenhuma nesta fase (Fase 0). Conforme as fases avançam, listar aqui:
SQLAlchemy (Fase 1), Flask-Login (Fase 2), etc.

## O que o Core expõe (`provides`)

A definir a partir da Fase 1 — `ModuleManager`, `EventBus`, RBAC,
`CrudGen`, `versioning`.

## Documentos relacionados

- [02-diagrama-c4.md](02-diagrama-c4.md)
- [03-fluxos.md](03-fluxos.md)
- [04-modelo-de-dados.md](04-modelo-de-dados.md)
- [05-casos-de-uso.md](05-casos-de-uso.md)
- [06-manutencao-e-expansao.md](06-manutencao-e-expansao.md)
