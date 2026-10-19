# Financeiro — revisão da consolidação e evidências de fechamento

Base atualizada: `eb50410` (as três entregas anteriores já incorporadas). Sem nova migração.

O patch reduz consultas desnecessárias entre as visões, inclui o atalho de volta ao dashboard de resultados, uniformiza a validação do contexto e oferece conferência de integridade e exportação JSON de cada versão do fechamento. Snapshot, histórico e regras monetárias permanecem preservados.

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-financeiro-revisao-consolidacao-entrega4.patch
python -m pytest tests/test_financeiro_consolidation_review.py tests/test_financeiro_result_closing.py tests/test_financeiro_accrual.py tests/test_financeiro_workspace.py tests/test_financeiro_reports.py tests/test_financeiro_cash_operations.py tests/test_sqlite_model_builder_foreign_keys.py -W error::sqlalchemy.exc.SAWarning -q
node tests/js/test_financeiro_workspace.cjs
node tests/js/test_financeiro_results.cjs
```

Reinicie a aplicação. Abra Financeiro → DRE e resultados; navegue entre as visões e volte pelo botão Dashboard de resultados. Em Conferência e fechamento, expanda uma versão, confira a integridade e exporte seu JSON. A exportação de versão reaberta mantém o snapshot original.

Os manuais `09-revisao-consolidacao.md` descrevem o comportamento e os contratos técnicos. Os testes automatizados cobrem navegação, filtros inválidos, catálogos grandes sem dependência indevida, autorização, organização, exportação somente por leitura e detecção de divergências sem modificar evidências. A inspeção visual local continua recomendada.
