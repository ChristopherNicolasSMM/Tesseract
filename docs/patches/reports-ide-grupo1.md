# Reports — IDE, grupo 1 (etapas 1–3)

Patch incremental sobre a entrega HTML/impressão já validada e o main
5f26a1af69fde296ca77a8a384b4deebedbc0cb5. Não reaplicar patches anteriores.

Entrega propriedades visuais tipadas, formatos declarativos, formulário de
parâmetros na IDE e consumidores, árvore de seções, seleção no canvas,
duplicação de subárvores, ordenação de irmãos e seção de destino.

```powershell
git am --keep-cr .\tesseract-reports-ide-grupo1.patch
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py tests/test_reports_styles.py tests/test_reports_formats.py tests/test_reports_sections.py -q
```

Se Node estiver disponível, validar operações puras da árvore:

```powershell
node --test tests/browser/reports_layout.test.cjs
```

Sem migration ou novas dependências de produção. Reiniciar o aplicativo e
recarregar /reports/ para obter os scripts atualizados. HTML continua padrão;
WeasyPrint permanece opcional e requer suas bibliotecas nativas.

Teste manual: criar seção, adicionar texto, duplicar, mudar destino para
Documento, salvar/reabrir, visualizar, publicar e clonar. Verificar folha
cinza azulada no tema escuro e branca na impressão. Editor indica estrutura;
a prévia usa dados resolvidos. Não inclui arrastar/soltar, desfazer, imagens,
colunas de composição ou PDF automático sem runtime nativo.
