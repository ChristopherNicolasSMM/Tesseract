# 01 — Visão Geral (Addon BrewStation)

## Propósito

Addon de domínio para gestão de cervejaria caseira. Núcleo do Addon
ainda não tem model próprio (root/ vazio) — toda a lógica até aqui
vive na Feature `yeast_bank`.

## Dependências

Nenhuma (`requires: []` no `addon.json`).

## O que expõe (`provides`)

`recipe_data`, `inventory_data` (declarado no manifesto, ainda sem
implementação — entram quando o núcleo do Addon ganhar models reais).

## Features

- `feature_yeast_bank` — ver `features/feature_yeast_bank/docs/technical/01-visao-geral.md`
