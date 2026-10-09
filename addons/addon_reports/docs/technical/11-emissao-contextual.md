# Emissão contextual nos addons

## Navegação

A IDE mantém seu menu gerado pelas anotações do modelo. Reports acrescenta
catálogo opcional de emissão com parent_code para os grupos existentes dos
addons. O proprietário dessas transações é reports, preservando seu desligamento
junto ao módulo e sem criar tabela/menu manual no banco. A descoberta padrão
registra o blueprint report_emission; não há alteração no Core/CrudGen.

| Menu | URL | Fonte/contrato |
| --- | --- | --- |
| BrewStation → Relatórios → Receitas | /brewstation/reports/receitas | reports.library.recipe.v1; receita completa e checklist |
| BrewStation → Relatórios → Sessões | /brewstation/reports/sessoes | reports.library.session.v1; etapas, logs e alarmes |
| BrewStation → Relatórios → Banco de leveduras | /brewstation/reports/banco-leveduras | reports.library.yeast.v1 |
| BrewStation → Relatórios → Disponibilidade e validade | /brewstation/reports/disponibilidade-validade | reports.library.expiry.v1 |
| BrewStation → Relatórios → Starters | /brewstation/reports/starters | reports.library.starters.v1 |
| BrewStation → Relatórios → Dashboard | /brewstation/reports/dashboard | reports.library.dashboard.v1 |
| Estoque → Relatórios → Estoque atual | /estoque/reports/estoque | estoque.organizacao.saldos.v1 |

Menus são contribuídos quando addon/feature de origem está registrado. A folha
exige report_templates.render. Ao abrir a tela ou usar a API, são exigidos também
todas as permissões .list das fontes; não exige acesso de edição à IDE.
O context processor só mostra os botões de origem se essa autorização completa
passar. Cada requisição verifica novamente addon/feature/permissões. Organização
segue o contrato global do projeto, sem introduzir isolamento de tenant novo.

## Filtros

Receitas: selecionar receita; sessão: selecionar sessão com planta associada.
Banco: status registrado, cepa e localização. Validade: cepa, localização, janela
inteira de 0–365 dias e data ISO de referência (padrão UTC); somente itens active.
Starters: status planned/active, cepa e intervalo inclusivo de start_date; sem
data é excluído quando há intervalo. Dashboard: busca por nome/cepa/localização
nas listas; indicadores permanecem globais e isso está indicado na tela.
Estoque: organização obrigatória, material opcional e somente saldo positivo.
Filtros são aplicados no servidor, com rejeição de campos desconhecidos/tipos
inválidos. Não modificam registros nem executam processos de negócio.

GET /api/reports/emission/<screen> devolve seletores, valores de filtros e
modelos ativos publicados compatíveis. POST no mesmo endereço recebe template,
version, options, filters, parameters e format. Exige o CSRF existente do Reports.
O servidor verifica chave/versão no catálogo compatível, consulta dados atuais e
chama generate_report. Nenhum sample_data do modelo é usado ou salvo na emissão.
Não há publicação automática. Os parâmetros seguem o formulário compartilhado,
com JSON avançado para valores compostos. Respostas de dados/HTML são no-store.

## Estoque organizacional

O novo build_organization_stock_report_data pertence ao Estoque: lê seus próprios
OrganizationBalance/Material em sessão de leitura e retorna JSON com organização,
unidade-base, moeda e valores já expostos por balance.to_dict. Limite de 2.000
linhas, rejeitando excesso sem truncar. Não refaz cotação, não converte moedas e
não movimenta saldo. Organizações inativas podem ser consultadas para histórico.
A leitura é autorizada por saldos.list + materials.list, conforme a consulta atual.

Novo modelo pronto estoque-organizacional na IDE. Selecione organização ao
carregar dados de exemplo. O estoque-atual anterior e estoque.saldos.v1 continuam
legados e não aparecem nesta emissão organizacional. O dashboard anterior ainda
identifica sua contagem de saldos como legada; não é consolidado organizacional.

## Botões e impressão

Receita: detalhe CRUD e aba Receita têm receita/checklist. Sessão: detalhe CRUD
e aba Sessões têm relatório detalhado com session_id + plant_id. O antigo botão
modal de sessão foi substituído, mas o consumer simples/API continua disponível.
Painel e listagens do banco têm links de banco/validade/starters; dashboard da
planta tem relatório geral; estoque organizacional tem relatório com organização
pré-selecionada. Todos abrem a mesma tela do menu. O botão Checklist sugere
ready.checklist-receita quando publicado; modelos personalizados continuam
selecionáveis pelo usuário.

A tela herda core/base.html, Bootstrap/NiceAdmin, ícones bi e tema ativo. Prévia
usa iframe sandbox sem scripts e helper compartilhado. Papel dark #273549 na
prévia; impressão branca por CSS do compositor. Imprimir / salvar PDF usa o
navegador, sem instalar WeasyPrint/Pango. Alterar filtros/modelo/parâmetros
invalida a prévia. Controles ficam travados durante a geração. Nenhum pacote ou
migration novo; reinicie para sincronizar menus.

Persistem os limites de leitura não paginada da biblioteca para BrewStation.
A emissão é uma consulta no momento da geração, sem garantia de snapshot
transacional entre múltiplas fontes. Não certifica viabilidade nem cria starters.

## Verificação da entrega

A rodada conjunta de Reports, estoque organizacional, transferências e prévia
organizacional passou com 309 testes e 10 subtestes (um WeasyPrint opt-in
não habilitado). A permissão de emissão sem acesso à IDE recebeu teste adicional.
Os 11 testes Node de layout/histórico passaram. O navegador verificou criação e
publicação dos nove modelos, emissão nas sete telas, impressão, invalidação ao
alterar filtro, atalho contextual de sessão e papel cinza azulado no tema escuro.
Fixtures são de banco descartável; dados reais do ambiente do usuário não foram
consultados ou alterados. Os testes de Workspace e painel do banco também foram
executados para conferir os templates de origem.
