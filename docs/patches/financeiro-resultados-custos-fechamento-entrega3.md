# Financeiro — entrega 3: resultados, custos e fechamento

Base: `ea1abde`. Migração: `a93dbe671ca5`.

Esta entrega consolida dashboard de resultados, custos disponíveis no Estoque e fechamento gerencial dentro de Resultados, preservando classificação, competência e histórico da entrega anterior. Inclui emissão pelo Reports, versões de fechamento/reabertura e correção da causa do SAWarning do Model Builder, inclusive em bancos já afetados.

Aplicação:

```bash
git am tesseract-financeiro-resultados-custos-fechamento-entrega3.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_result_closing.py tests/test_sqlite_model_builder_foreign_keys.py tests/test_financeiro_accrual.py tests/test_financeiro_reports.py -W error::sqlalchemy.exc.SAWarning -q
node tests/js/test_financeiro_results.cjs
```

Reinicie o aplicativo após aplicar. Consulte os manuais `08-resultados-custos-fechamento.md` em `addons/addon_financeiro/docs/manual` e `technical`. O fechamento declara cobertura gerencial e não presume receita ou CMV. Consumo produtivo/envase capitalizado não gera outra despesa. Reabertura é explícita e preserva versões anteriores. O downgrade recusa remover tabelas com fechamentos.
