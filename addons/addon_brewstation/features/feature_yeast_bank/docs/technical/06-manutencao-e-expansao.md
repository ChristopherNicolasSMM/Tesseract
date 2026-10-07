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

- `yeast_bank_items.recalculate_viability` implementa o cálculo linear por
  item. O serviço respeita lixeira, contaminação e ciclo de vida do starter.


## Serviço manual de integridade — 07/10/2026

`services/yeast_integrity_service.py` centraliza create/update/trash/restore/
delete_permanent. Os sete services gerados chamam overrides preservados nos
hooks; seu template já suporta essas extensões. Regenerar nunca deve remover
as regras manuais. `_apply_fields` do gerador é reutilizado com colunas filtradas,
readonly e hooks de cálculos/identificação, dentro de no_autoflush e tratamento
de rollback. O hook de controller do evento apenas escolhe o destino de leitura.

Criação de evento e efeitos tem um único commit. Não há deduplicação de POSTs
independentes, controle de genealogia, reserva física ou movimentação de estoque.
Vínculos históricos impedem exclusão permanente; soft-delete do evento não é
estorno de descarte. Não alterar esses contratos no CrudGen para todas as entidades.

A referência da contagem exige origem compatível e disponível quando vinculada.
Starters antigos sem status continuam compatíveis, enquanto novos starters
nascem planned. Prioridade real/estimado/starter/cepa e modelo linear mantidos.
Recálculo é explícito, transacional e pode limpar estimativa sem referência.
Ver o pacote `docs/patches/yeast-bank-integridade-eventos-viabilidade.md` na raiz
para regras, testes, permissões e limites.
