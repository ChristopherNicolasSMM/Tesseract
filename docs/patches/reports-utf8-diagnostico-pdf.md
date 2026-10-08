# Relatórios — UTF-8 e diagnóstico do worker PDF

> Roteiro da entrega anterior. O modo padrão evoluiu para HTML e impressão pelo navegador; consultar [reports-html-impressao.md](reports-html-impressao.md). PDF no servidor é opcional.

Correção incremental sobre o MVP de Relatórios entregue em 08/10/2026.
Sem migration nova. Aplicar depois do patch do MVP.

## Problemas observados

O teste leu JSON UTF-8 com a codificação padrão da máquina e produziu
`SacarificaÃ§Ã£o` em Windows. As três leituras dos exemplos nos testes agora
especificam `encoding='utf-8'`. O endpoint de exemplos já usava UTF-8 explícito.

Os outros cinco erros enviados retornam 503 porque o worker não gerou PDF.
Esse retorno sozinho não identifica a causa. Pango/DLL, dependência Python,
timeout ou outra falha precisam ser distinguidos no ambiente que falhou.
Não se declara a emissão Windows corrigida sem diagnóstico e nova execução.

O serviço registra categoria fixa/exit code e o comando de diagnóstico,
sem registrar HTML, dados do relatório ou stderr da geração de negócio.
O diagnóstico usa o mesmo Python e worker real com HTML fictício e mostra
dependências/erro nativo no console, sem abrir banco ou carregar dados reais.
Os testes PDF existentes continuam exigindo geração real, sem skip nem mock
para esconder as falhas observadas.

## Aplicação e diagnóstico (PowerShell, venv ativo)

```powershell
git am --keep-cr .\tesseract-reports-utf8-diagnostico-pdf.patch
python -m addons.addon_reports.root.services.report_pdf_diagnostics
```

Execute no mesmo venv e ambiente em que inicia o Tesseract. O diagnóstico
retorna zero apenas se WeasyPrint --info e o worker emitirem resultado válido.
Copie a saída se houver falha: ela identifica a etapa que terminou com erro.

Se indicar DLL/Pango ausente, verificar MSYS2 UCRT64 conforme o roteiro original.
No terminal MSYS2:

```text
pacman -S mingw-w64-ucrt-x86_64-pango
```

No PowerShell, ajustando ao diretório real:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
python -m addons.addon_reports.root.services.report_pdf_diagnostics
```

Se indicar dependência Python ausente, instalar no venv atual:

```powershell
python -m pip install -r addons/addon_reports/requirements.txt
```

Depois de o diagnóstico passar:

```powershell
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py -q
```

Reiniciar a aplicação no ambiente onde as DLLs estejam configuradas. Variável
definida em um PowerShell não altera outro processo já aberto.

## Validação

Linux: 41 testes e 10 subtestes passaram em 13,60 s. Diagnóstico executou
WeasyPrint --info e worker com saída zero; PDF fictício válido de 3848 bytes.
Logs de falha testados para não incluir HTML nem stderr/dados recebidos.
Windows e emissão local permanecem pendentes de confirmação.

## Diagnóstico confirmado no Windows

Após aplicar este patch, o usuário executou o diagnóstico no venv de produção:
WeasyPrint --info e o worker retornaram código 1, com erro 0x7e ao carregar
libgobject-2.0-0 e WEASYPRINT_DLL_DIRECTORIES não configurado. Isso confirma
a indisponibilidade da biblioteca nativa ao processo; a correção do ambiente
ainda precisa ser validada. O prefixo de stdout b'\r\n---' corresponde ao
aviso de importação do WeasyPrint, não a um PDF válido.

Instalar MSYS2 e executar pacman -S mingw-w64-ucrt-x86_64-pango no terminal
MSYS2 UCRT64. Depois, no PowerShell do venv:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
Test-Path "$env:WEASYPRINT_DLL_DIRECTORIES\libgobject-2.0-0.dll"
python -m addons.addon_reports.root.services.report_pdf_diagnostics
```

Ajustar o caminho se MSYS2 foi instalado em outro local. Test-Path deve retornar
True; o diagnóstico deve informar código zero nas duas etapas e valid: True.
Então repetir a suíte indicada acima e iniciar a aplicação nesse ambiente.

Para persistir a variável para novos processos do usuário:

```powershell
[Environment]::SetEnvironmentVariable('WEASYPRINT_DLL_DIRECTORIES', 'C:\msys64\ucrt64\bin', 'User')
```

Reabrir o terminal e reiniciar a aplicação após persistir. Serviços executados
por outra conta precisam receber a configuração em seu próprio ambiente.
Referência: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html
