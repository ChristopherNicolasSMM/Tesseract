# Competência e DRE — contratos e integridade

Migração `f82cad560b94`, parent `e71b9d45fa83`. Cinco tabelas novas com prefixo
`tesseract_financeiro_`: result_classification, accrual_entry, accrual_allocation,
accrual_reversal, accrual_active. As quatro primeiras são eventos imutáveis no
ORM e não permitem escrita por CrudGen; a última é o seletor operacional de
origem ativa, removido somente no estorno. Títulos/baixas não são regravados.

Classificação é versionada por categoria, com vigência mensal, grupo, motivo,
autor, request e snapshot. Reconhecimento congela classificação, política de
origem, valor, moeda, categorias e centros; apropriações são Decimal/texto
exato. Uniques protegem versões, chaves e origem ativa. Não há SUM numérico
sobre strings nem arredondamento silencioso das apropriações.

## Serviços e APIs

`accrual_service`: classify, recognize, preview, reverse, review, statement.
Escritas compartilham transação/rollback da Tesouraria, sem commits aninhados.
Prévia chama a mesma validação sem reserva/flush/commit e executa só SELECT.

`/api/financeiro/results`:

- POST `/classifications`: organization_code, category_id, expected_version
  (0 inicial), group_code, valid_from (primeiro dia do mês), reason, idempotency_key.
- POST `/recognitions` e `/recognitions/preview`: organization_code,
  source_type (TITLE, SETTLEMENT, ADJUSTMENT), source_id (null para ajuste),
  component (null ou INTEREST/FINE/DISCOUNT/FX/ROUNDING), reference,
  classification_id, effect (RECOGNIZE ou REDUCE para ajuste), amount,
  currency_code, policy_version_id (null obrigatório para origem registrada),
  reason, idempotency_key, allocations [{period:AAAA-MM,cost_center_id,amount}].
- POST `/recognitions/<id>/reverse`: reason, idempotency_key.
- GET `/dre`: organization_code, date_from/date_to obrigatórios; cost_center_id
  e group_code opcionais. Centro filtra todo o demonstrativo; grupo filtra
  somente a composição. Datas selecionam meses inteiros.
- GET `/review`: organization_code obrigatório.

Escritas exigem admin; consultas exigem financial_results.list. Campos extras,
IDs bool/float, moedas incompatíveis, centros de outra organização, versões
incompatíveis, datas inválidas e rateios inexatos são recusados. Preview e
consultas não movimentam caixa/estoque. Reenvio de evento estornado não o reativa;
reenvio de estorno antigo não remove reapresentação posterior.

## Origem e concorrência

`title:<id>` reconhece/exclui o principal integral pelo base_amount congelado,
sem depender de parcelas ou pagamentos. `settlement:<id>:<component>` reconhece
um componente não zero da baixa, pelo valor base congelado e direção financeira
compatível. `adjustment:<reference>` registra ajuste administrativo explícito.
Ajustes diferentes não têm deduplicação semântica de evidência econômica;
a responsabilidade da referência/motivo permanece na revisão administrativa.

Reconhecimentos e estornos reservam primeiro o título de origem, depois a
categoria e os centros em ordem de ID quando necessário. A revisão de
classificação reserva categoria. As guardas de cancelamento e estorno de baixa
usam a mesma reserva do título antes de consultar origens ativas. Isso serializa
as disputas e impede origem invalidada com reconhecimento ativo. Uniques são
a proteção final; qualquer falha desfaz evento, linhas e seletor juntos.

Compras de estoque com source_reference purchase:* só admitem NON_RESULT nesta
fase; não se presume CMV ou consumo a partir do pagamento. Competência não é
inferida de issue_date ou due_date. Componentes não repetem carrying_base do
principal. FX/ROUNDING congelados são classificados pelo sinal e tipo da baixa.

## DRE e histórico

`statement(options)` entrega `financeiro.dre.v1`: rows mensais/acumulado,
items achatados para Reports, details rastreáveis, pending_count, status PARTIAL
e basis. Usa estado atual dos reconhecimentos ativos, com estorno reapresentando
os meses originais. Não oferece consulta temporal "as of" ou
certificação de cobertura contábil. O fechamento gerencial está descrito no manual técnico 08. NON_RESULT aparece com efeito zero.

Intervalo de consulta até 366 dias; até 120 linhas por reconhecimento;
fontes do demonstrativo limitadas a 10.000 registros. Revisão limita títulos,
baixas e pendências a 2.000, sem truncamento silencioso. Origens já reconhecidas
saem da revisão; componentes zero, títulos cancelados e baixas estornadas não
entram. Pendências são globais da organização, não apenas do recorte de centro.

O workspace acrescenta quatro visões na aba DRE e resultados. A anotação de
AccrualEntry gera a permissão padrão; seu atalho automático é desativado pelo
manifesto, preservando uma única entrada de workspace. Reports consome somente
o contrato público via cash_flow_service.report_data('dre',options), sem ORM
financeiro. O exemplo financeiro-dre é instalado mas não publicado silenciosamente.

## Migração e próxima etapa

Upgrade valida todas as tabelas existentes antes de DDL e é repetível no esquema
inicializado. Downgrade é recusado quando qualquer uma das cinco tabelas contém
dados. Os registros anteriores permanecem sem reconhecimento presumido.

A entrega 3 acrescenta dashboard de resultados, custos disponíveis e fechamento
após conferência. Consulte o manual técnico 08 para esses contratos.

A entrega seguinte acrescenta dashboard, integração explícita de custos e fechamento gerencial: consulte [08-resultados-custos-fechamento.md](08-resultados-custos-fechamento.md).
