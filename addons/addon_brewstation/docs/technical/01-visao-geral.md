# 01 — Visão Geral (Addon BrewStation)

## Propósito

Addon de domínio para gestão de cervejaria caseira. Núcleo do Addon
ainda não tem model próprio (`root/` vazio) — toda a lógica vive em 3
Features.

## Dependências

Nenhuma (`requires: []` no `addon.json`).

## O que expõe (`provides`)

`recipe_data`, `inventory_data` (declarado no manifesto, ainda sem
implementação própria do núcleo — as Features já cobrem isso na
prática).

## Features

| Feature | Entidades | Docs |
|---|---|---|
| `feature_yeast_bank` | 8 | `features/feature_yeast_bank/docs/technical/01-visao-geral.md` |
| `feature_device_manager` | 4 | `features/feature_device_manager/docs/technical/01-visao-geral.md` |
| `feature_mash_control` | 12 | `features/feature_mash_control/docs/technical/01-visao-geral.md` |

FK cross-Feature existente: `feature_mash_control` referencia
`DeviceFunction` (`feature_device_manager`) — permitido por serem do
mesmo Addon (skill 02).

## Fora de escopo

`integ_bfather` (integração com a API do BrewFather) — aguardando
reescrita dedicada, não migrado do BrewStation original.
