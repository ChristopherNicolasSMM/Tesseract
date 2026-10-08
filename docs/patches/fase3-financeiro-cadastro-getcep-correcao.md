# Fase 3 — correção de cadastro, menu Financeiro e GetCEP

Corretivo sobre o pacote `tesseract-fase3-financeiro-organizacoes-getcep.patch`.
Implementado e testado no ambiente de geração; aplicação/conferência local
**deste corretivo** pendentes. A entrega inicial não é considerada validada:
o usuário reportou problemas de consulta CEP, padrão de telas/menu e perda de
valores ao salvar. Fundação de organizações anterior continua validada.

## Causas verificadas e correções

| Reporte | Evidência/limite da reprodução | Correção |
|---|---|---|
| CEP sem consulta/mensagem | JS anterior só consultava no blur/clique, criava controles no cliente e concatenava URL desde a raiz; não havia estado visível se não inicializasse. Não se reproduziu a ausência de consulta com os mesmos arquivos em navegador isolado e transporte simulado | Controle/estado explícito na organização, consulta também após 450ms de digitação completa, início por DOM/foco, URL fornecida por Flask (prefixos), asset versionado fora da API e mensagens visíveis |
| Cadastro/lista fora do padrão | Lista original continha todos os formulários de edição; não usava toolbar/paginação/componentes Core | Listagem tabular, novo cadastro expansível, busca/paginação/CSV/Excel, detalhe Ver / Editar e responsáveis com tabela/collapse, usando componentes administrativos existentes |
| Dados desapareciam ao salvar | Controller redirecionava mesmo quando serviço rejeitava entrada; dados enviados não voltavam para o HTML. Checkbox omitido virava False | Renderizar erro 422/409 com DTO + entrada submetida, manter banco anterior, preservar campos/estado omitidos e usar marcador de desmarcação explícita |
| Menu financeiro fora do addon | AddonFinanceiro sobrescrevia get_transactions com FIN_SETUP e campo group; árvore atual usa parent_code/default por modelos | Herança exata dos defaults de AddonBase/ModuleBase; endpoints {plural}.list, APIs em root/api/routes, grupo/folhas automáticos e inativação da entrada obsoleta |

Ajuste complementar: formulários de responsáveis usam acesso por chave,
compatível com DTO dict e ORM. IDs e valores de edição inválida são preservados.
Não recuperar dados perdidos no banco sem evidência/backup: a reprodução
comprovada foi de entrada não salva descartada após erro. Nenhum snapshot,
custo, ledger, organização/identidade ou valor monetário histórico foi alterado.

## Contratos preservados e rotas

- Core: GET `/admin/organizations/`, novo GET `/admin/organizations/<id>`;
  POST e APIs anteriores mantidos, sempre admin. Perfil omitido preservado;
  vazio/NULL explicitamente enviado continua limpeza de campo opcional.
- Export Core: GET `/admin/organizations/export.csv` e `.xlsx`, respeitando busca.
- Financeiro: `/financeiro/currencies/` e `/financeiro/monetary-policies/`,
  endpoints `currencies.list` e `monetary_policies.list`, permissões de leitura
  correspondentes. Escrita/API administrativa continuam admin; roles somente
  com leitura não recebem os controles de cadastro.
- `/financeiro/` permanece compatível (302 para moedas). Política/catálogo
  continuam imutáveis; API e cálculo Decimal existentes preservados.
- Menu: `TX_GROUP_AUTO_FINANCEIRO`, `TX_AUTO_CURRENCIES`,
  `TX_AUTO_MONETARY_POLICIES`, ícones por annotations. Financeiro não declara
  manualmente models/routes/get_transactions. Registro pelo loader padrão.
- `deprecated_transactions: ["FIN_SETUP"]` no manifesto: sync inativa só o
  registro do source_module financeiro, sem excluir linhas/referências nem
  alterar outros módulos. Não há menu duplicado na próxima inicialização.
- GetCEP: API GET `/api/plugins/getcep/<cep>` mantida; asset preferencial
  `/plugins/getcep/static/getcep.js?v=1.0.1`, MIME JavaScript. Asset anterior
  em `/api/plugins/getcep/assets/getcep.js` permanece compatível.
- Status, erros e campos usam text-muted/form-control/form-select/components
  existentes; preferência real `data-theme` e style_dark.css, sem tema paralelo.

Nenhum arquivo gerado pelo CrudGen foi editado. Templates/controllers novos
são manuais do Core/addon, com componentes compartilhados; não foi necessária
regeneração. Sem upgrade de dependências ou alteração de schema/migration.

## Aplicação PowerShell

Sobre a primeira parte financeira já aplicada, parar a aplicação:

```powershell
git -c gc.auto=0 am --keep-cr .\tesseract-fase3-financeiro-cadastro-getcep-correcao.patch
```

**Sem novo flask db upgrade**, desde que a migration financeira inicial
b82d9e43a017 já tenha sido aplicada. Reinicie a aplicação para registrar rotas,
sincronizar árvore e inativar FIN_SETUP. Reabra a página; Ctrl+F5 se ainda
aparecer conteúdo antigo. Não descartar alterações locais para aplicar patch.

## Roteiro local

Use o host/porta da instalação (exemplo `http://localhost:5000`).

1. `/admin/organizations/`: conferir tabela/busca/export/paginação; expandir
   Nova organização; preenchimento deve seguir grid/cards do Core.
2. Ver / Editar leva a `/admin/organizations/<id>`; conferir todos os valores
   da organização já criada, incluindo endereço/contato e responsáveis.
3. Em endereço vazio, digitar `01001-000` e aguardar, ou Consultar CEP: estado
   de consulta e retorno devem aparecer; número/complemento continuam manuais.
   Endereço preenchido é preservado; sugestão informa o retorno. API indisponível
   ou CEP ausente precisa exibir mensagem, sem limpar campos.
4. Enviar e-mail inválido na organização: mensagem no formulário e todos os
   valores digitados mantidos. Corrigir, salvar e recarregar; conferir persistência.
   Erro em responsável também deve manter nome/função/CPF/contato submetidos.
5. `/estoque/enderecos/`: expandir Novo registro e testar CEP nos campos reais.
   Dados existentes continuam manuais; não alterar quantidade/custos para testar.
6. Sidebar Financeiro: conferir Moeda/Política monetária dentro da pasta do
   addon, sem antigo item isolado. Conferir `/financeiro/currencies/` e
   `/financeiro/monetary-policies/`, novo cadastro expansível e listas.
7. Preferência claro/escuro: conferir labels, inputs, hints, erros, tabelas,
   badges e botões nas duas telas. Usuário comum sem permissão não deve acessar;
   role somente com lista pode ler, sem cadastrar via UI ou API.

## Ambiente e testes

Ambiente isolado Python **3.12.14**; requirements existente instalado sem
alterações: **41 versões fixadas conferem**, incluindo Alembic 1.18.4,
Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.51 e pytest 9.1.1.
`pip check`: **No broken requirements found.** Isso não certifica Windows/
PostgreSQL ou banco instalado. Não houve upgrade do arquivo de dependências.

Comando principal no ambiente de geração:

```bash
/workspace/scratch/3a31c61fc128/venv-corretivo/bin/python -m pytest tests/test_financeiro_ui_integrity.py tests/test_core_organizations.py tests/test_financeiro_foundation.py tests/test_migrations_idempotent.py tests/test_phase5_module_manager.py tests/test_module_discovery.py tests/test_admin_smart_list_parity.py tests/test_phase7a_transactions.py -q --tb=short --show-capture=no -W error::sqlalchemy.exc.LegacyAPIWarning
```

Resultado: **158 passed in 127.90s** (8 novos + 150 existentes).
Cobre preservação/rollback de cadastro, dados de responsáveis, paginação/export,
URLs com prefixo, menu automático/retirada restrita, APIs/permissões, contratos
monetários e cadeia Alembic. Testes da fundação atualizados só onde o contrato
de UI/menu mudou; teste do override manual limita a checagem aos módulos que
realmente têm override, permitindo outros addons automáticos legítimos.

```bash
node tests/test_getcep_ui.cjs
node --check plugins/plugin_getcep/static/getcep.js
```

**7 cenários Node aprovados**, script real/DOM mínimo/rede controlada:
preenchimento sem perda, corridas, falha, formato/país, país alterado durante
consulta, aliases Core e debounce/URL com prefixo. Syntax check exit 0.

Teste adicional `tests/test_financeiro_browser.cjs`, com Playwright e Chromium
153.0.8010.0 isolados do projeto (não entram nas dependências de runtime):
HTML/assets/respostas HTTP despachados pelo Flask test_client em SQLite memória.
Executa scripts e formulários nativos, CEP/sucesso/404/503 visíveis, erro de
validação e retomada sem perda, persistência após save, cadastro gerado de
endereços do Estoque, árvore automática e preferência real claro/escuro.
ViaCEP simulado; não confundir com certificação do servidor/proxy instalado.

Exemplo de comando no ambiente de geração:

```bash
TEST_PYTHON=/workspace/scratch/3a31c61fc128/venv-corretivo/bin/python TEST_CHROMIUM=/workspace/scratch/3a31c61fc128/browser-completo/chromium NODE_PATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules node tests/test_financeiro_browser.cjs
```

Para executar localmente, usar Node com playwright disponível e Chromium
instalado (`TEST_CHROMIUM` opcional se o Chromium padrão do Playwright existe);
`TEST_PYTHON` aponta ao Python do venv do Tesseract. Esses caminhos de teste não
são configuração do produto nem requisito para usar o GetCEP.

### Consulta real ao provedor — limite encontrado

Foi executada uma consulta sob demanda a `ViaCEP().lookup('01001000')`, sem
consultas em massa. Não foi possível certificar integração externa neste ambiente:

```text
LookupError 503 Consulta CEP indisponível. Preencha o endereço manualmente.
CAUSA: ReadTimeout(ReadTimeoutError("HTTPSConnectionPool(host='viacep.com.br', port=443): Read timed out. (read timeout=2)"))
```

Endpoint/provedor mantêm timeouts existentes; UI agora mostra falha/permite
salvar manualmente, comprovado pelo cenário HTTP 503 no navegador. Consulta
real deve ser conferida no servidor do usuário; não declarar sucesso externo
com base nos mocks. Duas falhas antigas do menu BrewStation, registradas no
relatório inicial, não foram reabertas nem incluídas nesta seleção.

## Base e empacotamento

O gitdir/venv antigos não sobreviveram à renovação do ambiente. Recuperada a
base a partir dos arquivos preservados, com **árvore exatamente igual** à
entrega financeira anterior: `0c934bcd3e6ba6ab7dd77819f3918bb955ac3ac6`.
O hash do commit reconstruído é diferente; não alegar recuperação do histórico.
Git format-patch gera somente o commit corretivo sobre esse conteúdo. Aplicação
isolada sobre a mesma árvore, igualdade de conteúdo e reverse --check são
conferidos antes de disponibilizar. Logo e arquivos alheios não fazem parte.

Próximas partes financeiras (taxas/conversão, contexto de compras/estoque e
liquidação) permanecem posteriores à validação local deste corretivo. Não
recalcular históricos ou atribuir moeda/organização ao legado.

## Verificação concluída do corretivo

Aplicação `git -c gc.auto=0 am --keep-cr` em checkout isolado da base
reconstruída: exit 0. Árvores do commit e checkout aplicado iguais;
`git apply --reverse --check`: exit 0; checkout limpo.
Repetição da seleção Python no checkout aplicado: **158 passed in 120.93s**.
Node: **7 cenários aprovados**. Chromium: fluxo completo aprovado, incluindo
CEP em Estoque, HTTP 404/503 visíveis, persistência e temas claro/escuro;
nenhum pageerror. A atualização final deste relatório não altera código.
Patch final regenerado e novamente conferido em checkout isolado: aplicação,
igualdade de árvores, reverse --check e diff --check.
