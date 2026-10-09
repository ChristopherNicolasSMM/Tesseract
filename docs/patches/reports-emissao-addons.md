# Reports — emissão nos addons

Base: main 11402e6 com tesseract-reports-modelos-operacionais.patch aplicado.
Patch incremental: não reaplica a biblioteca nem a correção de menu.

```powershell
git am --keep-cr .\tesseract-reports-emissao-addons.patch
python -m pytest tests/test_reports_emission.py tests/test_reports_library.py tests/test_reports_menu.py tests/test_reports_delivery.py -q
```

Sem migration/dependência. Reinicie para sincronizar menus.
BrewStation → Relatórios → Receitas/Sessões/Banco de leveduras/Disponibilidade e
validade/Starters/Dashboard. Estoque → Relatórios → Estoque atual.
Publique modelos compatíveis na IDE antes de emitir; para estoque, crie o novo
modelo pronto Estoque por organização e publique. Os antigos modelos de saldo
legado permanecem e não são aceitos nessa nova consulta.

Valide filtros, atalhos de receita/sessão, organização correta e impressão.
Documentação completa: addons/addon_reports/docs/technical/11-emissao-contextual.md.
