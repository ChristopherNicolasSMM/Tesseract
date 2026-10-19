# Entrega 3 — contratos financeiros de leitura e operação

Migração `e71b9d45fa83`, parent `d60a8c34e972`. Sete novas tabelas, prefixadas
`tesseract_financeiro_`: cash_transfer, cash_transfer_reversal, bank_statement,
bank_statement_line, bank_reconciliation, bank_reconciliation_undo e
bank_reconciliation_active. Eventos usam Money textual/Decimal e snapshots.
Somente a tabela de vínculos ativos é removível pelo serviço; eventos não são
editáveis/excluíveis pelo ORM/CrudGen. Upgrade pré-valida todas as tabelas
existentes antes de criar qualquer tabela. Downgrade recusa dados existentes.

`cash_operations_service` reutiliza transação, validações e post_cash da
Tesouraria sem chamar operações com commit aninhado. Transferências reservam
contas em ordem de ID; importação e conciliação reservam a conta. Uniques
protegem chaves e vínculos. O estorno transfere exatamente o valor original,
sem recotar. Falha em qualquer ponta desfaz evento, cache e movimentos.
SQLite foi exercitado com duas conexões; PostgreSQL não foi certificado aqui.

Novas operações exigem organização ativa; transferências/importações também
exigem contas ativas. Estornos e conciliações podem acessar contas inativas.
Consultas históricas aceitam organizações inativas. Idempotência compara o
pedido normalizado completo; reenvio de vínculo desfeito nunca o reativa, e
reenvio de desfazimento antigo nunca remove um vínculo posterior.

API administrativa: `/api/financeiro/operations`:

- GET `/cash-flow`, `/reconciliation`: organization_code, date_from/date_to
  ISO obrigatórios, account_id inteiro opcional.
- POST `/transfers`: organization_code, source_account_id,
  destination_account_id, amount decimal textual, operation_date,
  policy_version_id (null = v1), idempotency_key, notes (null permitido).
- POST `/transfers/<id>/reverse`: operation_date, reason, idempotency_key.
- POST `/statements/preview` e `/statements`: account_id, currency_code,
  reference, idempotency_key, lines [{external_id,operation_date,amount,description}].
- POST `/statement-lines/<id>/reconcile`: movement_id, idempotency_key,
  date_difference_reason (null quando datas iguais).
- POST `/reconciliations/<id>/undo`: reason, idempotency_key.

Não recebem autor do cliente; retornam envelope success/item/error. Campos
extras, float, bool como ID, datas inválidas e montantes fora de limites são
recusados. Preview de extrato e projeções executam somente SELECT.

`cash_flow_service.report_data(kind,options)` é o contrato público consumido
pelo Reports, que não importa ORM financeiro. Kinds: cash_flow, titles,
settlements, reconciliation. Contracts: financeiro.cash_flow.v1,
financeiro.titles.v1, financeiro.settlements.v1,
financeiro.reconciliation.v1. Retorna DTOs com decimais em strings, moeda base,
organização, datas e items. Todas as contas selecionadas pertencem à organização.

Consultas limitam intervalo a 366 dias, fontes de projeção/conciliação a
10.000 registros e relatórios a 2.000 linhas, sem truncamento silencioso.
O limite de movimentos considera também o histórico anterior necessário ao
saldo inicial; selecionar uma conta reduz esse volume. Relatórios possuem
adicionalmente os limites JSON do Reports. Não se usa SUM SQL sobre strings,
float monetário ou arredondamento implícito de transferência.

Reports contribui seu próprio subgrupo ao TX_GROUP_AUTO_FINANCEIRO. Cada
fonte exige addon ativo e respectiva permissão financeira de leitura, além
de report_templates.render para emitir. Fluxo exige também financial_titles.list
(pendências) e conciliação exige financial_movements.list (lançamentos). As
mesmas permissões de origem são verificadas nas telas financeiras. Datas são repassadas ao contrato
público antes da consulta. A geração usa versão publicada e renderer existente,
com valores exatos no formato raw. Os exemplos são instalados na IDE, sem
publicar modelos nem criar lançamentos automaticamente.

O fluxo é uma projeção operacional atual, não contabilidade por competência,
integração bancária, OFX/CNAB, previsão cambial ou reconstrução temporal das
baixas/cancelamentos. Os critérios de período e moeda constam também no manual.
