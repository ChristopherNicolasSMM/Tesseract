# Addon Relatórios — MVP da IDE e emissão contextual

> Roteiro da entrega anterior. O modo padrão evoluiu para HTML e impressão pelo navegador; consultar [reports-html-impressao.md](reports-html-impressao.md). PDF no servidor é opcional.

Pacote consolidado para `git am --keep-cr`. Base remota conferida em 08/10/2026:
`6b9b75f388de93887d584c154a19d4e0c1481fe4` (Financeiro/Organização/GetCEP).
O pacote contém somente Relatórios e suas integrações; não reaplica Financeiro.

## O que entra

- Addon `reports`, descoberta/menu/RBAC pelo Core; modelos, revisões e parâmetros.
- IDE `/reports/`: texto, tabela e divisor, vinculação de campos, propriedades,
  exemplos assistidos, salvar, prévia, publicação e clonagem.
- Publicação imutável pelo serviço, concorrência otimista e erro sem sobrescrita.
- Tema real do Core; folha escura `#273549`, clara e impressão brancas.
- Serviço Python e API JSON autenticada; PDF em subprocesso com limites e timeout.
- PDF do material no detalhe do saldo e PDF da sessão no Workspace da planta;
  catálogo de revisões compatíveis publicadas e parâmetros em JSON no modal.
- Contratos dos consumidores sem ORM/FK entre addons e sem refazer ledger/custos.
- Migration `c93e0f54b128`, filha de `b82d9e43a017`; valida/preserva catálogo
  compatível já criado no boot e recusa schema divergente.
- Manuais, documentação técnica, exemplos e testes Python/navegador.

## Aplicar no PowerShell, com o venv do Tesseract ativo

O checkout deve ter a base acima e não ter modificações pendentes nos arquivos
do pacote. Confira `git status` e `git log -1 --oneline` antes de aplicar.

```powershell
git am --keep-cr .\tesseract-reports-mvp.patch
python -m pip install -r addons/addon_reports/requirements.txt
python -m weasyprint --info
python run.py db upgrade
```

Instalar as dependências adicionais não altera o `requirements.txt` UTF-16 do
Core. WeasyPrint requer bibliotecas nativas: em Windows, usar MSYS2 UCRT64 e
instalar Pango pelo comando abaixo **no terminal MSYS2**, não no PowerShell:

```text
pacman -S mingw-w64-ucrt-x86_64-pango
```

Se `python -m weasyprint --info` não localizar DLLs, ajustar o diretório real
da instalação no PowerShell e repetir a verificação:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
python -m weasyprint --info
```

A variável localiza DLLs; as configurações de negócio permanecem em SystemConfig.
Reiniciar o Tesseract após instalar as dependências e executar a migration.
O downgrade da migration apaga o catálogo de Relatórios, inclusive seus dados.

## Testes locais

```powershell
python -m pytest tests/test_reports_bindings.py tests/test_reports_workspace.py tests/test_reports_consumers.py tests/test_reports_delivery.py tests/test_financeiro_foundation.py -q --tb=short
python -m pytest tests/test_plant_workspace.py tests/test_workspace_cycle_consolidation.py tests/test_addon_estoque.py tests/test_hide_legacy_mash_control_menu.py tests/test_theme_profile_roles_versioning.py -q --tb=short
```

Resultado da construção na mesma base: 112 testes e 10 subtestes na primeira
suíte, 464 testes na segunda (576 testes no total). Linux/SQLite aprovados;
Windows/PostgreSQL dependem da execução no ambiente final. Não declarar os testes
locais aprovados antes de executá-los.

Navegador opcional para repetir o percurso automatizado (Node necessário):

```powershell
npm ci --prefix tests/browser
node tests/browser/node_modules/playwright/cli.js install chromium --only-shell
python tests/browser/run_reports_browser.py
```

O runner inicia/encerra servidor e SQLite temporário somente em localhost:5068.
Credenciais e fixture de teste não são rotas do addon nem alteram o banco normal.

## Validação visual e de domínio

1. Abrir `/reports/`, criar modelo, carregar exemplo de Estoque e salvar.
2. Editar título/colunas/campos, conferir prévia e publicar explicitamente.
3. No detalhe de um saldo, usar **PDF do saldo deste material**; escolher modelo
   publicado e baixar PDF. O documento contém somente o material selecionado.
4. Criar/publicar um modelo pelo exemplo de Sessão de brassagem.
5. Abrir `/brewstation/plant-workspace/`, escolher planta e aba Sessões;
   selecionar uma sessão e usar **PDF desta sessão**.
6. Criar nova revisão e conferir preservação da revisão publicada anterior.
7. Alternar tema pelo perfil/Core: editor escuro com folha cinza azulada;
   PDF/prévia/impressão sempre brancos.

As ações exigem `report_templates.render` e permissões de domínio. IDE exige
`report_templates.list`, `detail` e as permissões da operação (create/update/
publish). Botões ficam ausentes quando Reports não está carregado ou faltam
permissões. Se o modal não tiver modelo, carregar e publicar o exemplo compatível.

## Limites deste MVP

Contratos/parâmetros ainda usam JSON; o canvas é estrutural, a prévia PDF é a
referência de impressão. Não há drag/drop, undo/autosave, HTML/Jinja livre,
assets, condições, catálogo reutilizável de widgets em banco, fila ou histórico
de emissões. O custo da sessão é o registro confirmado; `recipe_id` não promete
snapshot histórico inexistente. Emissão não executa alarmes/movimentações.

O limite de memória usa recursos Linux; no Windows permanece timeout do pai.
Não há promessa de PDF binariamente idêntico entre fontes/ambientes. Detalhes e
limites em `addons/addon_reports/docs/technical/06-manutencao-e-expansao.md`,
evidência em `07-validacao-e-pendencias.md`, contratos em
`08-integracao-consumidores.md`.

## Conferência do pacote

O arquivo de entrega é um único commit em formato mbox, adequado a `git am`.
A aplicação é conferida em checkout isolado na base remota acima; sua árvore
final deve ser idêntica à árvore do commit consolidado. Uma conferência reversa
com `git apply --reverse --check` verifica presença integral do diff aplicado.
Essa conferência não modifica o checkout do usuário nem envia commits ao remoto.
