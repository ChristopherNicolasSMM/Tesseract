# Reports — IDE, grupo 2 (etapas 4–6)

Entrega incremental sobre main fce9f257e8dbba5c2413a82ba9b2064ba443bf5d,
com o grupo 1 já aplicado. Inclui colunas de composição, PNG/JPEG incorporados
e página/paginação. Não reaplicar grupos/patches anteriores.

```powershell
git am --keep-cr .\tesseract-reports-ide-grupo2.patch
python -m pip install -r addons/addon_reports/requirements.txt
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py tests/test_reports_styles.py tests/test_reports_formats.py tests/test_reports_sections.py tests/test_reports_composition.py tests/test_reports_images.py tests/test_reports_pagination.py -q
node --test tests/browser/reports_layout.test.cjs
```

Pillow 12.3.0 é a nova dependência Python do addon, sem MSI/Pango para HTML.
Não exige db upgrade. Reinicie a aplicação e recarregue /reports/.
WeasyPrint permanece opcional e requer seu runtime nativo para PDF servidor.

## Conferência manual

1. Criar rascunho, usar Colunas de composição e inserir textos em cada seção filha.
2. Adicionar PNG/JPEG local até 128 KiB, conferir medidas/descrição/alinhamento e salvar/reabrir.
3. Abrir Página e impressão; testar A5 paisagem e margens. Numeração precisa de margem inferior >=8 mm.
4. Usar quebra antes de componente fora das colunas e visualizar.
5. Imprimir/salvar PDF com papel configurado, escala adequada e cabeçalhos/rodapés automáticos desativados quando usar numeração.
6. Conferir tabela longa, cabeçalho repetido, numeração e logotipo; alternar temas, mantendo impressão branca.
7. Publicar e clonar, confirmar bloqueio de edição e preservação da configuração.

Prévia HTML contínua; canvas não calcula folhas exatas. Manter inteiro é uma
preferência que pode ceder quando conteúdo não cabe. Não aceitar quebras
forçadas dentro das colunas; aplicá-las antes/depois do grupo. Tabelas muito
longas devem preferir fluxo normal. SVG/GIF/URLs e binding dinâmico de imagens
ficam fora desta entrega; catálogo de assets e blocos reutilizáveis seguem
planejados. Sem cabeçalho/rodapé customizado ou PDF automático sem runtime.

Validação local: 159 testes Python e 10 subtestes, seis testes Node, navegador
e PDFs Chromium aprovados. Tabela de 100 linhas preservada em 9 páginas A5
paisagem e 5 A4 retrato; numeração, cabeçalhos e imagem conferidos. Um teste
WeasyPrint opt-in desabilitado; diálogo Windows depende da validação local.
