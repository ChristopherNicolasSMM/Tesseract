# Reports — menu no padrão dos addons

Correção incremental após tesseract-reports-ide-grupo3.patch. Não reaplica
os grupos anteriores. Base de desenvolvimento: entrega do grupo 3 sobre
main d4dd0e8. URL /reports/ e permissões permanecem.

```powershell
git am --keep-cr .\tesseract-reports-menu-padrao.patch
python -m pytest tests/test_reports_menu.py tests/test_reports_workspace.py -q
```

Sem nova migration ou dependência. Reinicie a aplicação e recarregue a página:
Relatórios → Modelo de relatório. Se o upgrade do grupo 3 ainda estiver
pendente, execute-o conforme o roteiro daquele grupo; este ajuste não o substitui.

Menu gerado pelo ModuleBase a partir do modelo anotado, com endpoint .list
real e grupo automático. Entrada legada TX_REPORT_TEMPLATES é desativada pelo
sync do Core usando deprecated_transactions, somente quando source_module
é reports. Preserva registros, transações manuais e preferências do usuário;
preferências ligadas ao código legado não são migradas para os novos códigos.
Admin/usuário podem ajustar ordem e colapso nas telas padrão do Core.

Confira ausência de entrada solta duplicada, abertura de /reports/, temas,
permissões e manutenção dos modelos/versões/blocos. Revisões, parâmetros e
blocos são dados internos da IDE; não criam menus para CRUDs inexistentes.

Validação: 206 testes Python, 10 subtestes e Playwright/Chromium aprovados.
Um PDF WeasyPrint opt-in permaneceu desabilitado. Patch conferido com git am
em checkout isolado após grupo 3, com árvore idêntica e verificação reversa.
