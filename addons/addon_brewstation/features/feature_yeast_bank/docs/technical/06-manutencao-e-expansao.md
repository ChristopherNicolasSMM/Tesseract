# 06 — Manutenção e Expansão (Feature Yeast Bank)

## Adicionar um campo a `YeastStrain`

1. Editar `model/yeast_strain.py`.
2. `python run.py generate --model addons/addon_brewstation/features/feature_yeast_bank/model/yeast_strain.py --addon brewstation --feature yeast_bank --overwrite`
3. Hooks (`*_hooks.py`) preservados automaticamente.

## Migrar o restante do `yeast_bank` (Fase 5b)

Ordem sugerida, da tabela mais independente para a mais dependente
(registro histórico da migração original — Fase 5/5b; algumas
entidades citadas abaixo já mudaram de forma desde então, ver
`04-modelo-de-dados.md` pro estado atual):

1. `YeastStorageDevice` (sem FK para nada novo)
2. `YeastBankItem` (FK para `YeastStrain` e `YeastContainer`)
3. `YeastCellCountHistory`, `YeastBankEvent` (FK opcionais/obrigatórias para várias — `YeastStarterLog` foi fundida em `YeastBankEvent` na skill 22)
4. `YeastBankConfig` (sem FK, é configuração)

Cada uma segue o mesmo processo: anotar, `generate`, preencher docs.

## Pontos de extensão conhecidos

- `yeast_strains.recalculate_viability` já tem permissão sincronizada,
  só falta a implementação do cálculo (portar a lógica de
  `daily_viability_loss_pct` do BrewStation original).
