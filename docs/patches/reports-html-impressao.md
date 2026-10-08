# Relatórios HTML e impressão pelo navegador

Entrega autorizada: tesseract-reports-html-impressao.patch, incremental após
tesseract-reports-mvp.patch e tesseract-reports-utf8-diagnostico-pdf.patch.
Base incremental: MVP de Reports e correção UTF-8/diagnóstico já aplicados.
Sem migration adicional, sem instalador nativo e sem variável de ambiente para
o fluxo HTML. Templates existentes permanecem válidos.

## Contratos

- requirements.txt do addon exige somente jsonschema além do Core.
- requirements-pdf.txt mantém WeasyPrint opcional, com requisitos nativos próprios.
- Publicação valida o HTML e não exige PDF de exemplo.
- POST /api/reports/render e consumidores retornam text/html por padrão.
- POST preview retorna JSON com html por padrão, como já fazia com format=html.
- format=pdf explícito preserva emissão automática opcional.
- generate_report e helpers de domínio retornam str por padrão; consumidores
  Python que esperam bytes devem passar format="pdf".
- Autenticação, CSRF, RBAC, escopo, limites e imutabilidade permanecem.

## Validação local

```powershell
python -m pip install -r addons/addon_reports/requirements.txt
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py -q
```

O teste de emissão PDF real fica desabilitado nessa suíte por padrão. Para
validar também a capacidade opcional em ambiente com dependências instaladas:

```powershell
$env:REPORTS_TEST_PDF = '1'
python -m pytest tests/test_reports_workspace.py -q
```

Percurso manual: /reports/ → criar modelo → carregar exemplo → salvar → prévia
HTML → imprimir/salvar PDF → publicar → abrir saldo ou sessão → escolher modelo
→ abrir relatório → imprimir. Testar claro/escuro, A4, acentuação e tabela longa.
Prévia contínua não representa páginas exatas. Destino/local do PDF é escolha
do usuário; não há PDF automático retornado pelo servidor no modo HTML.

## Evidências desta rodada

44 testes e 10 subtestes aprovados em 88,97 s, sem WeasyPrint instalado;
1 teste de PDF real opcional desabilitado. Compilação Python, sintaxe JavaScript
e git diff --check aprovados. PDF produzido pelo Chromium: A4, duas páginas,
quebra explícita e texto final na página seguinte. Validação Windows ainda local.

Navegador aprovado: Playwright 1.51.1 / Chromium Headless Shell 134.
Edição/salvamento, exemplos, quebra de página, prévia HTML, folha escura,
impressão branca, publicação/imutabilidade, clonagem, conflito preservando
rascunho, viewport 390 px e consumidores Estoque/BrewStation com HTML e
acionamento de impressão. Sem pageerror. Confirmação automatizada aguarda
a transição Bootstrap; boot do servidor de teste aguarda até 60 s.

## Aplicação

```powershell
git am --keep-cr .\tesseract-reports-html-impressao.patch
python -m pip install -r addons/addon_reports/requirements.txt
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py -q
```

Reinicie a aplicação e confira /reports/. Nenhum db upgrade adicional.
origin/main reconferido em 6b9b75f; pacote não inclui alterações de outros addons
fora das ações/contratos de Reports. Nenhum push.
