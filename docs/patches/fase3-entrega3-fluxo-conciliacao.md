# Financeiro — entrega 3 de 3

Etapas 7 e 8: fluxo de caixa, transferências, conciliação bancária e relatórios.
Base: segunda entrega `9031393`. A main remota consultada estava em `86b621c`
(primeira entrega); aplique a entrega 2 antes deste patch. Não inclui refatoração
ampla nem altera o histórico anterior.

```powershell
git am --keep-cr .\tesseract-financeiro-entrega3-fluxo-conciliacao.patch
python run.py db upgrade
python -m pytest tests/test_financeiro_cash_operations.py tests/test_financeiro_reports.py tests/test_financeiro_treasury.py tests/test_reports_emission.py tests/test_reports_library.py tests/test_financeiro_ui_integrity.py -q
```

Reinicie a aplicação. Financeiro > Fluxo de caixa, Transferências financeiras,
Conciliação bancária; Relatórios aparece quando Reports está ativo. A emissão
exige modelo compatível publicado na IDE. Sem dependências adicionais.

Manual: addons/addon_financeiro/docs/manual/05-fluxo-conciliacao.md.
Contrato: addons/addon_financeiro/docs/technical/05-fluxo-conciliacao.md.

Validação: transferências/estornos atômicos, conflitos de chave, importação
sem movimento de caixa, duplicatas, vínculo exclusivo, desfazimento e novo
vínculo, moeda/organização, valores exatos, previsões e relatórios por DTO.
Seis cenários concorrentes cobrem repetição de transferência, disputa de saldo,
transferências opostas, importação, conciliação e desfazimento repetidos.

Cadeia Alembic conferida sobre esquema inicializado, upgrade repetido, criação
isolada das sete tabelas, rejeição de schema incompatível antes de DDL e
bloqueio de downgrade com dados. Sem certificação nativa Windows/PostgreSQL
ou inspeção visual em navegador; verificação funcional em Linux/SQLite.

Resultado: 230 casos distintos selecionados passaram (23 novos e 207 de
fundação monetária, câmbio, políticas, interface, tesouraria e relatórios).
Os checks afetados pelo ajuste de permissões foram repetidos: 19 passaram.
A migração completa, prévias somente SELECT, HTML dos quatro relatórios com
dados reais e preservação dos saldos foram conferidos. O aviso de reflexão
SQLite sobre a tabela Core model_definition não impediu o upgrade.

Patch conferido por git am --keep-cr em checkout isolado de 9031393,
verificação reversa e igualdade de árvore. As três entregas planejadas estão
concluídas; eventual refatoração deve ser avaliada separadamente.
