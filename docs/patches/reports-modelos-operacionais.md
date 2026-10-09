# Reports — modelos operacionais

Patch incremental após reports-ide-grupo3 e reports-menu-padrao (base b96d541).

```powershell
git am --keep-cr .\tesseract-reports-modelos-operacionais.patch
python -m pytest tests/test_reports_*.py -q
```

Sem nova migration/dependência. Reinicie a aplicação. Em Relatórios → Modelo
de relatório, escolha um dos oito modelos prontos, crie o rascunho, selecione
a fonte correspondente e carregue os dados reais. Confira a prévia e imprima.
Não são inseridos modelos automaticamente no banco durante boot.

Somente Reports, editor, testes e documentação mudam. Addons de origem não
são alterados. Estoque usa Saldo legado; validade é do banco de leveduras;
starters são eventos planejados/ativos já existentes. A sessão detalhada usa
contrato próprio, sem substituir o consumidor simples de sessão.

Documentação: addons/addon_reports/docs/technical/10-biblioteca-modelos-operacionais.md
e manual/03-funcionalidades.md.
