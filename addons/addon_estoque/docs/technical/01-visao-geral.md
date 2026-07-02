# 01 — Visão Geral (Addon Estoque)

## Propósito

Gestão genérica de materiais estocáveis — matéria-prima, embalagem,
kits/composições — com ledger de movimentação e saldo materializado.
Não conhece nenhum domínio de negócio específico; existe pra ser
dependência de qualquer Addon futuro que precise de controle de
estoque, sem reescrever a mesma lógica.

## Dependências

Nenhuma (`requires: []`) — é infraestrutura de base.

## O que expõe (`provides`)

- `material_data` — identidade e atributos de Material
- `stock_movement_data` — ledger de movimentações
- `stock_balance_data` — saldo atual por Material

Consumido por outros Addons **só via service público** (nunca FK
direta — skill 02). `addon_brewstation` é o primeiro consumidor
(`feature_mash_control` para resolução de ingredientes,
`feature_ingredientes`, `feature_envase`).

## Origem

Nasceu da análise do módulo legado `plugin_integ_bFather` (BrewStation
antigo, pré-Tesseract) — o bloco de `Embalagem`/`TipoEmbalagem`/estoque
de ingredientes daquele módulo não seguia a convenção do Tesseract
(criava tabela apesar de se chamar "plugin" — skill 00 proíbe isso) e
foi redesenhado do zero como este Addon.

## Documentos técnicos relacionados

`02-diagrama-c4.md`, `03-fluxos.md`, `04-modelo-de-dados.md`,
`05-casos-de-uso.md`.

## Pendências conhecidas

- Mecanismo de recálculo manual de saldo — sinalizado, não desenhado.
- Regra de bloqueio (ou não) de saída sem saldo suficiente — em aberto.
- `docs/manual/` deste Addon — ainda não escrito.
- `i18n/pt_BR.json` — ainda não escrito.
- Domínio de Cálculo/precificação (base de custo, base dedutiva,
  impostos cadastrados) que também vai consumir este Addon — parked,
  sessão dedicada futura.
