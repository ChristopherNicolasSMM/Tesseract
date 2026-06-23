# 01 — Visão Geral (Feature Yeast Bank)

## Propósito

Banco de cepas de levedura — identidade da cepa (`YeastStrain`) com
parâmetros de modelo de viabilidade (decaimento linear por padrão).

Portado de `plugin_yeast_bank` (BrewStation original). Esta primeira
fatia migra só `YeastStrain` — a entidade mais central e mais simples.
As demais 7 tabelas do plugin original (item físico do banco, starter,
storage device/reading, config, histórico de contagem, eventos) ficam
para a próxima leva (ver BACKLOG.md, "Fase 5b").

## Dependências

Nenhuma (`requires: []` no `feature.json`).

## O que expõe (`provides`)

`yeast_strain_data`.

## Tabela

`tesseract_brewstation_yeastbank_strain` — ver
`docs/technical/04-modelo-de-dados.md` (a criar quando o restante das
tabelas de yeast_bank entrar, para já nascer com o diagrama ER
completo em vez de um ER de tabela única).

## Permissões

7 automáticas (Camada 1: `yeast_strains.list/detail/create/update/
trash/restore/delete_permanent`) + 1 de negócio (Camada 2:
`yeast_strains.recalculate_viability`, ainda sem implementação —
só a permissão existe, a lógica de recálculo vem com o restante do
yeast_bank).
