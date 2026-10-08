# Manutenção e instalação

Dependências adicionais fixadas em addons/addon_reports/requirements.txt (jsonschema e WeasyPrint). Preservada a codificação UTF-16 do requirements.txt da raiz; não foi reformatado nem alterado. Instalação prevista: python -m pip install -r addons/addon_reports/requirements.txt, além dos requisitos do core. Dependências nativas/fontes do WeasyPrint precisam ser confirmadas no Windows e produção; somente Linux foi exercitado nesta construção.

Novas tabelas seguem create_all_pending_tables do projeto. Migration
`c93e0f54b128`, filha de `b82d9e43a017`, cria o catálogo ou valida e preserva as
tabelas compatíveis já criadas no boot. Divergência de colunas, tipos, PK/FKs,
unicidade ou CHECK bloqueia a migration sem mascarar o problema. Cabeça Alembic
única conferida. Depois da futura aplicação, executar `python run.py db upgrade`
antes de reiniciar. Downgrade remove o catálogo e seus dados; não é estratégia
de recuperação de templates. Nenhuma migração foi executada na instalação do usuário.

Configuração runtime em tesseract_system_config: reports.pdf_timeout_seconds (int, padrão 30, faixa 5–120), reports.pdf_memory_mb (int, padrão 1024, faixa 256–2048). Leitura por conexão curta; valor inválido retorna padrão. Não mantém a transação do chamador aberta para consultar configurações durante renderização.

Limites MVP: JSON 1 MiB, HTML 2 MiB, PDF 10 MiB; 200 elementos; profundidade de layout 8; caminhos 32; tabela 2000 registros; 12 colunas; 50 parâmetros. Dois workers simultâneos por processo web; capacidade excedida retorna 429. São limites iniciais conservadores, não um SLA medido.

Worker: stdin/stdout, timeout e finalização via subprocess.run, sem temporários persistidos. Em Linux usa RLIMIT_AS/RLIMIT_CPU; em Windows há timeout mas limite de memória dependerá de infraestrutura/Job Objects futura. URLs/file:// são bloqueados; componentes atuais não permitem inserir assets livres.

Styles: reports_editor.css somente na IDE. A folha clara é branca; folha escura #273549, texto #e8eef7. PDF possui CSS próprio branco e não recebe tema da sessão. A prévia PDF mostra documento branco mesmo com IDE escura.

Extensões precisam de contratos/renderers confiáveis e testes; nunca código Python/JS em tabelas. Atualizar docs junto da mudança. Atualizar novamente Git e integrar mudanças concorrentes antes do patch final, sem perder trabalho local. Não fazer push nem gerar patches intermediários.

## Integração Python e HTTP inicial

Contrato Python: generate_report(key, version=None, data=<JSON>, parameters=None) em root/services/report_template_service.py devolve bytes PDF. Requer contexto Flask/Login autorizado; snapshot usa leitura própria e não executa rollback/commit da sessão de negócio do consumidor. Concluir a transação de negócio antes de chamar. Alterações pendentes new/dirty/deleted são rejeitadas para evitar compartilhamento acidental de unidade de trabalho.

API autenticada por sessão do Core: login → GET /api/reports/session → usar csrf_token em X-Reports-CSRF → POST /api/reports/render com template, version opcional, data e parameters. Resposta application/pdf; modelo deve estar publicado. Autenticação por token externo independente ainda não foi implementada.

## Executar testes de navegador

```text
npm ci --prefix tests/browser
node tests/browser/node_modules/playwright/cli.js install chromium --only-shell
python tests/browser/run_reports_browser.py
```

Playwright 1.51.1 é dependência somente do teste, isolada de produção. O runner
cria SQLite temporário em arquivo, inicia o servidor em localhost:5068, aguarda
saúde, executa Node e encerra servidor/banco ao terminar. O banco em arquivo
evita compartilhar uma conexão SQLite em memória entre requisições paralelas.
Não usar a porta 5068 para outra aplicação durante o teste. Credenciais e a
rota de fixture existem somente no servidor descartável, não no addon.

## Perfil e Windows

Compilador: layout declarativo `schema_version=1`, A4/CSS fixos, WeasyPrint
70.0 e jsonschema 4.26.0; SQLAlchemy 2.0.51 alinhado aos requisitos atuais do
Core. Nesta execução: Python 3.12.14, Pango 1.52.1 e pydyf 0.12.1.
As versões transitivas, bibliotecas nativas e fontes não são congeladas por
revisão. `content_hash` identifica o conteúdo da revisão, não garante PDF
binariamente idêntico entre máquinas. Registro persistente de perfil/fontes
e histórico de emissão ficam para evolução posterior.

No Windows, este addon usa a biblioteca Python, portanto instalar apenas o
executável independente de WeasyPrint não atende ao worker. Com o venv do
Tesseract ativo, instalar `addons/addon_reports/requirements.txt`, Pango via
MSYS2 UCRT64 (`pacman -S mingw-w64-ucrt-x86_64-pango` no terminal MSYS2) e conferir
`python -m weasyprint --info`. Se as DLLs não forem localizadas, no PowerShell:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
python -m weasyprint --info
python -m pytest tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py -q
```

Essa variável localiza biblioteca nativa do sistema; as configurações de negócio
do addon continuam na tabela SystemConfig. Usar o diretório real da instalação.
Fonte consultada em 08/10/2026: [instalação oficial de WeasyPrint 70.0](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).
O roteiro está documentado, mas execução Windows e PostgreSQL continuam
dependendo da validação local/ambiente de implantação.
