# Validação e limites — 08/10/2026

## Base e escopo desta rodada

Construção inicial sobre fae21ed; rebase concluído sem conflitos sobre
origin/main/6b9b75f (Financeiro/Organização/GetCEP). O usuário autorizou a entrega
do patch; remoto reconferido em 08/10/2026, mantendo essa base. Não houve push
nem aplicação na instalação do usuário. Roteiro em
`docs/patches/reports-mvp-ide-integracao.md`.

Este corte contém catálogo/revisões/parâmetros, IDE de texto/tabela/divisor,
contratos e exemplos, concorrência otimista, publicação, clonagem, prévia e PDF,
serviço Python/API JSON, carregamento assistido dos exemplos e botões contextuais
no detalhe do saldo e na aba Sessões. Não é a conclusão de todas as evoluções
planejadas da IDE.

## Evidência automatizada

```text
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py tests/test_financeiro_foundation.py -q --tb=short
```

**112 testes e 10 subtestes passaram em 46,65 s.**

Verificados com Flask/SQLite e modelos reais: descoberta do addon, prefixos/FKs,
base/controles do Core, autenticação/RBAC, CSRF, persistência, defaults, conflito,
publicação, imutabilidade, clonagem, emissão, schema/escape/escopo, limites,
timeout e capacidade. Consumidores verificam custos registrados sem recalcular,
zero/null, exclusão, ordem, planta correta e preservação de alteração pendente.
Migration testada em criação nova, reexecução preservando conteúdo, compatibilidade
com os modelos do boot, rejeição de schema divergente e downgrade restrito às
três tabelas do catálogo. Alembic tem uma cabeça: c93e0f54b128.

```text
python -m pytest tests/test_plant_workspace.py tests/test_workspace_cycle_consolidation.py tests/test_addon_estoque.py tests/test_hide_legacy_mash_control_menu.py tests/test_theme_profile_roles_versioning.py -q --tb=short
```

**464 testes passaram em 597,44 s.** Total desta rodada: 576 testes e
10 subtestes aprovados nas duas suítes, além do percurso de navegador.

Compilação Python, sintaxe dos dois scripts JavaScript e git diff --check
aprovados. SQLAlchemy 2.0.51 alinhado ao Core desta base.

## Navegador e impressão

```text
python tests/browser/run_reports_browser.py
```

Percurso aprovado com Playwright 1.51.1 / Chromium Headless Shell 134:
criar, editar, salvar, recarregar, mover/remover, carregar exemplo, editar coluna
sem JSON manual, vincular campos, prévia PDF, publicar, bloquear edição publicada,
clonar e tratar conflito preservando rascunho. Também verificou o viewport móvel
390 px e os dois consumidores até o download de um PDF real, sem pageerror.

Temas foram alterados pela API do Core e recarregados, incluindo seu CSS real.
Folha escura computada rgb(39,53,73), texto rgb(232,238,247); clara e mídia print
rgb(255,255,255). Capturas claras/escuras inspecionadas: layout com base NiceAdmin,
controles Bootstrap, folha azul acinzentada, painel de propriedades com rolagem
própria e contraste dos botões ajustado no escopo da IDE.

O download do Chromium 151 falhou nas primeiras rodadas. Nesta rodada foi
resolvido por instalação isolada do Playwright 1.51.1/Headless Shell 134, sem
mudar as dependências de produção. O runner usa SQLite em arquivo temporário
para não compartilhar conexão em memória entre requisições paralelas.

PDF fictício de 150 registros verificado anteriormente: 6 páginas, registro
final na última página, cabeçalhos, acentuação, numeração e papel branco.

## Limites e validação local

Linux/SQLite foram exercitados; PostgreSQL, Windows, limites de memória Windows
e fontes do ambiente final ainda exigem validação. Roteiro e dependências nativas
Windows em 06-manutencao-e-expansao.md. Não se promete identidade binária de PDF
entre ambientes. Catálogo compartilhado usa RBAC; Organização não é tenant.

O consumidor lê os registros atuais persistidos; não produz histórico imutável
nem snapshot de receita inexistente na sessão. Leituras múltiplas não garantem
isolamento snapshot em todos os bancos. Emissão não recalcula ledger/custos.

HTML/Jinja avançado, assets, condições, drag/drop, undo/autosave, formulário de
parâmetros tipado, catálogo reutilizável de blocos/widgets em banco, fontes/perfil
persistido do compilador, fila e histórico de emissões seguem como evolução.
Este corte não importa essa funcionalidade como se estivesse pronta.

Entrega autorizada: pacote consolidado, conferência de aplicação em checkout
limpo e roteiro local. Nenhum push. A validação da instalação do usuário continua
pendente, mesmo após aplicação conferida em checkout isolado.

## Retorno Windows e correção incremental

Usuário informou seis falhas: uma de acentuação na leitura de exemplo e cinco
de worker PDF/HTTP 503. Leituras agora usam UTF-8 explícito; diagnóstico local
do worker acrescentado, sem expor dados do request nos logs/API. Linux: 41
testes e 10 subtestes passaram; smoke do worker real também passou. A causa
dos 503 no Windows depende da saída desse diagnóstico; não é dada como
resolvida pelo teste Linux. Roteiro em docs/patches/reports-utf8-diagnostico-pdf.md.
