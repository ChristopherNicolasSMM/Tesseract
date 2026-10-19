# Contratos de resultados e fechamento

- `result_dashboard_service.dashboard`: DTO `financeiro.results_dashboard.v1`, calculado a partir de `accrual_service.statement`, com comparativo mensal, indicadores, margens e tabelas. Valores monetários são strings decimais. Percentuais sem denominador válido são nulos. Reports consome o mesmo contrato público, com `financial_results.list`.
- `addon_estoque.root.services.financial_cost_data.list_cost_sources`: DTO `estoque.financial_costs.v1`; Financeiro não importa ORM do Estoque. Fontes `STOCK` exigem destinação e classificação explícitas. Capitalização, transferências e reversões são excluídas conservadoramente. Uma reversão posterior de origem reconhecida gera `SOURCE_CHANGED`, exigindo estorno/revisão financeira explícita.
- `result_closing_service`: fechamento/reabertura append-only e cache de fechamento ativo. Lock da política monetária da organização serializa fechamento, reconhecimento e estorno. Preview faz apenas consultas. Chaves idempotentes comparam a solicitação inteira antes de retornar um evento anterior. Snapshot canônico e digest preservam a evidência original.

GET `/api/financeiro/results/dashboard` e `/costs` exigem `financial_results.list`. POST `/close` e `/closures/<id>/reopen` exigem `admin`. As páginas, apropriações e conferência permanecem sob a navegação integrada do workspace. O fechamento não impede a criação de origens operacionais: pendências retroativas alteram o status de conferência, sem reescrever snapshots.

## Migração e warning SQLite

Revisão `a93dbe671ca5`, pai `f82cad560b94`, cria três tabelas de fechamento. Valida tabelas preexistentes antes do DDL e bloqueia downgrade com dados. Não reintroduz defeitos de FK no downgrade.

O warning de `parent_model_definition_id` vinha de FKs equivalentes, uma sem nome e outra nomeada, duplicadas pela migração `d4e0a26f9c31`. A verificação histórica passa a comparar também a assinatura da FK; os modelos usam nomes estáveis. Para bancos já afetados, a nova migração lê `PRAGMA foreign_key_list`, deduplica por assinatura e recria somente as duas tabelas afetadas, preservando colunas, dados, índices e constraints. Não há filtro de warnings. Como outras recriações batch do SQLite, o reparo exige `foreign_keys=OFF` antes da transação e recusa prosseguir se estiver ligado.

Validação inclui upgrade completo com SAWarning como erro, reparo de banco duplicado populado, reflexão sem warning e `foreign_key_check`, fechamento/reabertura idempotentes, exclusão de capitalização, dashboard/Reports, autorização e disputa entre fechamento e estorno em conexões independentes.
