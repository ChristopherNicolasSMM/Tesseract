# 06 — Manutenção e Expansão (Feature Yeast Bank)

## Adicionar um campo a `YeastStrain`

1. Editar `model/yeast_strain.py`.
2. `python run.py generate --model addons/addon_brewstation/features/feature_yeast_bank/model/yeast_strain.py --addon brewstation --feature yeast_bank --overwrite`
3. Hooks (`*_hooks.py`) preservados automaticamente.

## Migrar o restante do `yeast_bank` (Fase 5b)

Ordem sugerida, da tabela mais independente para a mais dependente:

1. `YeastStorageDevice` (sem FK para nada novo)
2. `YeastStorageReading` (FK para `YeastStorageDevice`)
3. `YeastBankItem` (FK para `YeastStrain` e `YeastStorageDevice`)
4. `YeastStarterLog` (FK para `YeastBankItem`)
5. `YeastCellCountHistory`, `YeastBankEvent` (FK opcionais para várias)
6. `YeastBankConfig` (sem FK, é configuração)

Cada uma segue o mesmo processo: anotar, `generate`, preencher docs.

## Pontos de extensão conhecidos

- `yeast_strains.recalculate_viability` já tem permissão sincronizada,
  só falta a implementação do cálculo (portar a lógica de
  `daily_viability_loss_pct` do BrewStation original).
